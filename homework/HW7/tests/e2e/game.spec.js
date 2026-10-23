const { test, expect } = require("@playwright/test");

const GROUND_Y = 330;

async function snapshot(page) {
  return page.evaluate(() => window.__dinoRun.snapshot());
}

async function openAndStart(page) {
  await page.goto("/");
  await expect(page.locator("#overlayTitle")).toHaveText("按空白鍵開始");
  await page.keyboard.press("Space");
  await expect(page.locator("#overlay")).toHaveClass(/hidden/);
  await expect.poll(async () => (await snapshot(page)).score).toBeGreaterThan(0);
}

test.describe("DINO RUN 網站", () => {
  test("首頁載入、排行榜連線、無 JS 錯誤", async ({ page }) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
    page.on("console", (message) => {
      if (message.type() === "error") {
        errors.push(`console: ${message.text()}`);
      }
    });

    await page.goto("/");
    await expect(page).toHaveTitle(/DINO RUN/);
    await expect(page.locator("#overlayTitle")).toHaveText("按空白鍵開始");
    await expect(page.locator("#game")).toBeVisible();
    await expect(page.locator("#netBadge")).toHaveText("排行榜連線");
    await expect(page.locator("#lbStatus")).not.toHaveText("載入中…");
    await page.waitForTimeout(500);
    expect(errors).toEqual([]);
  });

  test("鍵盤控制：開始、跳躍、蹲下、暫停與繼續", async ({ page }) => {
    await openAndStart(page);
    const initial = await snapshot(page);
    expect(initial.state).toBe("running");
    expect(initial.dino.onGround).toBe(true);
    expect(initial.dino.y).toBe(GROUND_Y);

    await page.keyboard.press("ArrowUp");
    await expect.poll(async () => (await snapshot(page)).dino.onGround).toBe(false);
    const jumped = await snapshot(page);
    expect(jumped.dino.y).toBeLessThan(GROUND_Y);
    await expect
      .poll(async () => (await snapshot(page)).dino.onGround, { timeout: 4000 })
      .toBe(true);

    await page.keyboard.down("ArrowDown");
    await expect.poll(async () => (await snapshot(page)).dino.ducking).toBe(true);
    await page.keyboard.up("ArrowDown");
    await expect.poll(async () => (await snapshot(page)).dino.ducking).toBe(false);

    await page.keyboard.press("p");
    await expect.poll(async () => (await snapshot(page)).state).toBe("paused");
    await expect(page.locator("#overlayTitle")).toHaveText("遊戲暫停");
    await expect(page.locator("#pauseBtn")).toHaveText("繼續");

    await page.keyboard.press("p");
    await expect.poll(async () => (await snapshot(page)).state).toBe("running");
    await expect(page.locator("#overlay")).toHaveClass(/hidden/);
  });

  test("遊戲結束後可送出分數並更新排行榜", async ({ page, request }) => {
    await openAndStart(page);
    await expect(page.locator("#overlayEyebrow")).toHaveText("GAME OVER", {
      timeout: 15000,
    });

    const finalScore = (await snapshot(page)).score;
    expect(finalScore).toBeGreaterThan(0);
    await expect(page.locator("#nameRow")).toBeVisible();
    await expect(page.locator("#overlayTitle")).toContainText(String(finalScore));

    const playerName = `E2E${Date.now().toString().slice(-8)}`;
    await page.locator("#nameInput").fill(playerName);
    await page.locator("#saveBtn").click();

    await expect(page.locator("#saveMsg")).toContainText("已存入排行榜");
    await expect(page.locator("#saveBtn")).toHaveText("已送出");
    await expect(page.locator("#lbList")).toContainText(playerName);

    const response = await request.get("/api/scores?limit=50");
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(
      data.scores.some((row) => row.name === playerName && row.score === finalScore)
    ).toBeTruthy();
  });

  test("排行榜會顯示 SQLite 中的既有資料", async ({ page, request }) => {
    const seedName = `Seed${Date.now().toString().slice(-8)}`;
    const response = await request.post("/api/scores", {
      data: { name: seedName, score: 999999 },
    });
    expect(response.status()).toBe(201);

    await page.goto("/");
    await expect(page.locator("#lbList li").first()).toContainText(seedName);
    await expect(page.locator("#lbList li").first()).toContainText("999999");
  });

  test("Service Worker 離線後仍可載入並開始遊戲", async ({ page, context }) => {
    await page.goto("/");
    await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
    if (!(await page.evaluate(() => Boolean(navigator.serviceWorker.controller)))) {
      await page.reload();
    }
    await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));

    const cached = await page.evaluate(async () => {
      const keys = await caches.keys();
      const cache = await caches.open(keys[0]);
      const requests = await cache.keys();
      return requests.map((request) => new URL(request.url).pathname);
    });
    expect(cached).toEqual(
      expect.arrayContaining([
        "/",
        "/index.html",
        "/style.css",
        "/game.js",
        "/manifest.webmanifest",
        "/icon.svg",
      ])
    );

    try {
      await context.setOffline(true);
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page).toHaveTitle(/DINO RUN/);
      await expect(page.locator("#game")).toBeVisible();
      await expect(page.locator("#netBadge")).toHaveText("離線模式");
      await page.keyboard.press("Space");
      await expect(page.locator("#overlay")).toHaveClass(/hidden/);
      await expect.poll(async () => (await snapshot(page)).score).toBeGreaterThan(0);
    } finally {
      await context.setOffline(false);
    }
  });
});

test.describe("手機版", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("觸控按鈕可開始遊戲並跳躍", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#jumpBtn")).toBeVisible();
    await expect(page.locator("#duckBtn")).toBeVisible();

    await page.locator("#startBtn").tap();
    await expect(page.locator("#overlay")).toHaveClass(/hidden/);
    await expect.poll(async () => (await snapshot(page)).score).toBeGreaterThan(0);

    await page.locator("#jumpBtn").tap();
    await expect.poll(async () => (await snapshot(page)).dino.onGround).toBe(false);
    expect((await snapshot(page)).dino.y).toBeLessThan(GROUND_Y);
  });
});
