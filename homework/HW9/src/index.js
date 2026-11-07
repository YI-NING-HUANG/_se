const MAX_BODY = 16 * 1024;
const MAX_SCORE = 1_000_000;
const MAX_NAME = 16;
const MAX_LIMIT = 50;
const CONTROL_CHARS = /[\x00-\x1f\x7f]/g;

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400",
};

const JSON_HEADERS = {
  ...CORS_HEADERS,
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
};

export function cleanName(raw) {
  if (typeof raw !== "string") {
    return null;
  }
  const name = raw.replace(CONTROL_CHARS, " ").replace(/\s+/g, " ").trim();
  const length = [...name].length;
  if (length < 1 || length > MAX_NAME) {
    return null;
  }
  return name;
}

export function validScore(raw) {
  if (typeof raw !== "number" || !Number.isInteger(raw)) {
    return null;
  }
  if (raw < 0 || raw > MAX_SCORE) {
    return null;
  }
  return raw;
}

export function parseLimit(raw) {
  if (raw === null || raw === undefined || raw === "") {
    return 10;
  }
  if (!/^\d+$/.test(raw)) {
    return null;
  }
  return Math.max(1, Math.min(Number(raw), MAX_LIMIT));
}

function json(payload, status = 200, extraHeaders = {}, head = false) {
  return new Response(head ? null : JSON.stringify(payload), {
    status,
    headers: { ...JSON_HEADERS, ...extraHeaders },
  });
}

function methodNotAllowed(allow) {
  return json({ ok: false, error: "不支援的 HTTP 方法" }, 405, { Allow: allow });
}

function notFoundPage() {
  return new Response(
    "<!doctype html><meta charset=utf-8><title>404</title>" +
      "<h1>404 Not Found</h1><p><a href=/>回到 DINO RUN</a></p>",
    {
      status: 404,
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "X-Content-Type-Options": "nosniff",
      },
    }
  );
}

async function readStats(env) {
  const row = await env.DB.prepare(
    "SELECT COUNT(*) AS games, COALESCE(MAX(score), 0) AS best, " +
      "COALESCE(AVG(score), 0) AS average FROM scores"
  ).first();
  return {
    games: Number(row.games || 0),
    best: Number(row.best || 0),
    average: Math.round(Number(row.average || 0) * 10) / 10,
  };
}

async function getScores(url, env, head) {
  const limit = parseLimit(url.searchParams.get("limit"));
  if (limit === null) {
    return json({ ok: false, error: "limit 必須是整數" }, 400, {}, head);
  }
  try {
    const [top, stats] = await Promise.all([
      env.DB.prepare(
        "SELECT id, name, score, created_at FROM scores " +
          "ORDER BY score DESC, id ASC LIMIT ?"
      )
        .bind(limit)
        .all(),
      readStats(env),
    ]);
    return json(
      { ok: true, scores: top.results || [], stats },
      200,
      {},
      head
    );
  } catch (error) {
    console.error("D1 getScores failed", error);
    return json(
      { ok: false, error: "資料庫暫時無法使用" },
      500,
      {},
      head
    );
  }
}

async function getStats(env, head) {
  try {
    return json({ ok: true, stats: await readStats(env) }, 200, {}, head);
  } catch (error) {
    console.error("D1 getStats failed", error);
    return json({ ok: false, error: "資料庫暫時無法使用" }, 500, {}, head);
  }
}

async function postScore(request, env) {
  const declaredLength = Number(request.headers.get("content-length") || 0);
  if (declaredLength > MAX_BODY) {
    return json({ ok: false, error: "請求內容過大" }, 413);
  }

  let text;
  try {
    text = await request.text();
  } catch {
    return json({ ok: false, error: "無法讀取請求內容" }, 400);
  }
  if (new TextEncoder().encode(text).byteLength > MAX_BODY) {
    return json({ ok: false, error: "請求內容過大" }, 413);
  }
  if (!text) {
    return json({ ok: false, error: "缺少請求內容" }, 400);
  }

  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    return json({ ok: false, error: "JSON 格式錯誤" }, 400);
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    return json({ ok: false, error: "JSON 必須是物件" }, 400);
  }

  const name = cleanName(payload.name);
  if (name === null) {
    return json({ ok: false, error: "名字長度需為 1 到 16 個字" }, 400);
  }
  const score = validScore(payload.score);
  if (score === null) {
    return json(
      { ok: false, error: "分數需為 0 到 1000000 的整數" },
      400
    );
  }

  const createdAt = new Date().toISOString();
  try {
    const inserted = await env.DB.prepare(
      "INSERT INTO scores (name, score, created_at) VALUES (?, ?, ?)"
    )
      .bind(name, score, createdAt)
      .run();
    const id = Number(inserted.meta.last_row_id);
    const rankRow = await env.DB.prepare(
      "SELECT COUNT(*) + 1 AS rank FROM scores " +
        "WHERE score > ? OR (score = ? AND id < ?)"
    )
      .bind(score, score, id)
      .first();
    return json(
      {
        ok: true,
        record: { id, name, score, created_at: createdAt },
        rank: Number(rankRow.rank),
      },
      201
    );
  } catch (error) {
    console.error("D1 postScore failed", error);
    return json({ ok: false, error: "資料庫暫時無法使用" }, 500);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;
    const head = request.method === "HEAD";

    if (request.method === "OPTIONS" && path.startsWith("/api/")) {
      return new Response(null, {
        status: 204,
        headers: {
          ...CORS_HEADERS,
          "Cache-Control": "no-store",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }

    if (path === "/api/health") {
      if (request.method !== "GET" && !head) {
        return methodNotAllowed("GET, HEAD");
      }
      return json(
        {
          ok: true,
          service: "dino-run",
          version: "2.0",
          runtime: "cloudflare-workers",
          database: "d1",
        },
        200,
        {},
        head
      );
    }

    if (path === "/api/scores") {
      if (request.method === "GET" || head) {
        return getScores(url, env, head);
      }
      if (request.method === "POST") {
        return postScore(request, env);
      }
      return methodNotAllowed("GET, HEAD, POST");
    }

    if (path === "/api/stats") {
      if (request.method !== "GET" && !head) {
        return methodNotAllowed("GET, HEAD");
      }
      return getStats(env, head);
    }

    if (path.startsWith("/api/")) {
      return json({ ok: false, error: "找不到這個 API" }, 404);
    }

    return notFoundPage();
  },
};
