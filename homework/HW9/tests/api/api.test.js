import test from "node:test";
import assert from "node:assert/strict";

const BASE_URL = process.env.BASE_URL || "http://127.0.0.1:8788";

async function call(path, options = {}) {
  const response = await fetch(BASE_URL + path, options);
  const text = await response.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  return { response, body, text };
}

function postScore(payload) {
  return call("/api/scores", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

test("GET /api/health 回報 Cloudflare Worker 與 D1", async () => {
  const { response, body } = await call("/api/health");
  assert.equal(response.status, 200);
  assert.equal(body.ok, true);
  assert.equal(body.service, "dino-run");
  assert.equal(body.runtime, "cloudflare-workers");
  assert.equal(body.database, "d1");
});

test("GET /api/scores 初始為空且 stats 歸零", async () => {
  const { response, body } = await call("/api/scores");
  assert.equal(response.status, 200);
  assert.equal(body.ok, true);
  assert.deepEqual(body.scores, []);
  assert.deepEqual(body.stats, { games: 0, best: 0, average: 0 });
});

test("API 回應使用 no-store 與 nosniff", async () => {
  const { response } = await call("/api/scores");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.match(response.headers.get("content-type"), /application\/json/);
});

test("HEAD 請求不帶 body", async () => {
  const health = await fetch(BASE_URL + "/api/health", { method: "HEAD" });
  assert.equal(health.status, 200);
  assert.equal(await health.text(), "");
  const scores = await fetch(BASE_URL + "/api/scores", { method: "HEAD" });
  assert.equal(scores.status, 200);
  assert.equal(await scores.text(), "");
});

test("首頁與靜態資源由 Cloudflare Static Assets 提供", async () => {
  const index = await call("/");
  assert.equal(index.response.status, 200);
  assert.match(index.text, /DINO RUN/);
  assert.match(index.text, /Cloudflare Workers \+ D1/);

  const game = await call("/game.js");
  assert.equal(game.response.status, 200);
  assert.match(game.response.headers.get("content-type"), /javascript/);

  const sw = await call("/sw.js");
  assert.equal(sw.response.status, 200);
  assert.match(sw.text, /api\//);
  assert.match(sw.text, /dino-run-v2\.0\.0/);
});

test("未知 API 與未知頁面回傳 404", async () => {
  const api = await call("/api/unknown");
  assert.equal(api.response.status, 404);
  assert.equal(api.body.ok, false);

  const page = await call("/no-such-page");
  assert.equal(page.response.status, 404);
  assert.match(page.response.headers.get("content-type"), /text\/html/);
});

test("OPTIONS preflight 允許跨網域的單檔前端", async () => {
  const preflight = await fetch(BASE_URL + "/api/scores", {
    method: "OPTIONS",
    headers: {
      Origin: "https://yi-ning-huang.github.io",
      "Access-Control-Request-Method": "POST",
      "Access-Control-Request-Headers": "content-type",
    },
  });
  assert.equal(preflight.status, 204);
  assert.equal(preflight.headers.get("access-control-allow-origin"), "*");
  assert.match(
    preflight.headers.get("access-control-allow-methods"),
    /POST/
  );
  assert.match(
    preflight.headers.get("access-control-allow-headers"),
    /Content-Type/i
  );

  const get = await call("/api/scores", {
    headers: { Origin: "https://yi-ning-huang.github.io" },
  });
  assert.equal(get.response.headers.get("access-control-allow-origin"), "*");
});

test("不支援的 HTTP 方法回傳 405 與 Allow", async () => {
  for (const method of ["PUT", "PATCH", "DELETE"]) {
    const { response, body } = await call("/api/scores", { method });
    assert.equal(response.status, 405);
    assert.equal(body.ok, false);
    assert.match(response.headers.get("allow"), /POST/);
  }
  const health = await call("/api/health", { method: "POST" });
  assert.equal(health.response.status, 405);
});

test("POST 拒絕非法名字", async () => {
  const cases = [
    {},
    { name: "", score: 10 },
    { name: "   ", score: 10 },
    { name: 123, score: 10 },
    { name: "字".repeat(17), score: 10 },
  ];
  for (const payload of cases) {
    const { response, body } = await postScore(payload);
    assert.equal(response.status, 400, JSON.stringify(payload));
    assert.equal(body.ok, false);
    assert.match(body.error, /名字/);
  }
});

test("POST 拒絕非法分數", async () => {
  const cases = [
    { name: "Neo", score: -1 },
    { name: "Neo", score: 1_000_001 },
    { name: "Neo", score: 1.5 },
    { name: "Neo", score: "10" },
    { name: "Neo", score: true },
    { name: "Neo" },
  ];
  for (const payload of cases) {
    const { response, body } = await postScore(payload);
    assert.equal(response.status, 400, JSON.stringify(payload));
    assert.equal(body.ok, false);
    assert.match(body.error, /分數/);
  }
});

test("POST 拒絕壞 JSON、非物件與過大內容", async () => {
  const malformed = await call("/api/scores", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{oops",
  });
  assert.equal(malformed.response.status, 400);
  assert.match(malformed.body.error, /JSON 格式/);

  const array = await postScore([1, 2, 3]);
  assert.equal(array.response.status, 400);
  assert.match(array.body.error, /物件/);

  const huge = await postScore({ name: "x".repeat(20_000), score: 1 });
  assert.equal(huge.response.status, 413);
  assert.match(huge.body.error, /過大/);

  const empty = await call("/api/scores", { method: "POST", body: "" });
  assert.equal(empty.response.status, 400);
  assert.match(empty.body.error, /缺少請求內容/);
});

test("POST 寫入 D1 並回傳排名與紀錄", async () => {
  const { response, body } = await postScore({ name: "Alice", score: 120 });
  assert.equal(response.status, 201);
  assert.equal(body.ok, true);
  assert.equal(body.rank, 1);
  assert.equal(body.record.name, "Alice");
  assert.equal(body.record.score, 120);
  assert.ok(body.record.id > 0);
  assert.match(body.record.created_at, /^\d{4}-\d{2}-\d{2}T/);

  const list = await call("/api/scores");
  assert.equal(list.body.scores.length, 1);
  assert.deepEqual(list.body.scores[0], body.record);
  assert.deepEqual(list.body.stats, { games: 1, best: 120, average: 120 });
});

test("名字會清洗、同分依先後排名、高分排第一", async () => {
  const cleaned = await postScore({ name: "  Neo\n", score: 100 });
  assert.equal(cleaned.response.status, 201);
  assert.equal(cleaned.body.record.name, "Neo");
  assert.equal(cleaned.body.rank, 2);

  const top = await postScore({ name: "Zoe", score: 500 });
  assert.equal(top.body.rank, 1);

  const tie = await postScore({ name: "Tie", score: 120 });
  assert.equal(tie.body.rank, 3);

  const list = await call("/api/scores");
  assert.deepEqual(
    list.body.scores.map((row) => `${row.name}:${row.score}`),
    ["Zoe:500", "Alice:120", "Tie:120", "Neo:100"]
  );
  assert.deepEqual(list.body.stats, { games: 4, best: 500, average: 210 });
});

test("limit 參數會驗證、夾限並只回傳前 N 名", async () => {
  const bad = await call("/api/scores?limit=abc");
  assert.equal(bad.response.status, 400);

  const one = await call("/api/scores?limit=1");
  assert.equal(one.response.status, 200);
  assert.deepEqual(
    one.body.scores.map((row) => row.name),
    ["Zoe"]
  );

  const zero = await call("/api/scores?limit=0");
  assert.equal(zero.body.scores.length, 1);

  const many = await call("/api/scores?limit=999");
  assert.equal(many.body.scores.length, 4);
});

test("GET /api/stats 與排行榜統計一致", async () => {
  const stats = await call("/api/stats");
  assert.equal(stats.response.status, 200);
  assert.equal(stats.body.ok, true);
  assert.deepEqual(stats.body.stats, {
    games: 4,
    best: 500,
    average: 210,
  });
});
