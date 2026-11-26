const path = require("path");
const { defineConfig } = require("@playwright/test");

const PORT = 8799;
const PYTHON = process.env.PYTHON || "python";

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: /.*\.spec\.js/,
  timeout: 30000,
  expect: { timeout: 7000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  outputDir: path.join(__dirname, "test-results", "artifacts"),
  reporter: [
    ["list"],
    ["html", { outputFolder: path.join(__dirname, "playwright-report"), open: "never" }],
    ["json", { outputFile: path.join(__dirname, "test-results", "results.json") }],
  ],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel: "chrome",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  webServer: {
    command: `"${PYTHON}" ../../app.py --host 127.0.0.1 --port ${PORT} --db .tmp/e2e.db`,
    cwd: __dirname,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 30000,
    stdout: "ignore",
    stderr: "ignore",
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  },
});
