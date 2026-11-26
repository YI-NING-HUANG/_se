import test from "node:test";
import assert from "node:assert/strict";

import { cleanName, parseLimit, validScore } from "../../src/index.js";

test("cleanName 接受正常名字並保留 Unicode", () => {
  assert.equal(cleanName("Alice"), "Alice");
  assert.equal(cleanName("小明"), "小明");
  assert.equal(cleanName("🦖 Dino"), "🦖 Dino");
});

test("cleanName 去除控制字元並合併空白", () => {
  assert.equal(cleanName("  A   B  "), "A B");
  assert.equal(cleanName("A\nB\tC"), "A B C");
  assert.equal(cleanName("\u0000Neo\u007f"), "Neo");
});

test("cleanName 以 Unicode code point 計算 16 字上限", () => {
  assert.equal(cleanName("🦖".repeat(16)), "🦖".repeat(16));
  assert.equal(cleanName("🦖".repeat(17)), null);
  assert.equal(cleanName("字".repeat(16)), "字".repeat(16));
  assert.equal(cleanName("字".repeat(17)), null);
});

test("cleanName 拒絕空字串、空白與非字串", () => {
  assert.equal(cleanName(""), null);
  assert.equal(cleanName("   "), null);
  assert.equal(cleanName(null), null);
  assert.equal(cleanName(123), null);
  assert.equal(cleanName({ name: "Neo" }), null);
});

test("validScore 只接受 0 到 1000000 的整數", () => {
  assert.equal(validScore(0), 0);
  assert.equal(validScore(1_000_000), 1_000_000);
  assert.equal(validScore(42), 42);
  assert.equal(validScore(-1), null);
  assert.equal(validScore(1_000_001), null);
  assert.equal(validScore(1.5), null);
  assert.equal(validScore("10"), null);
  assert.equal(validScore(true), null);
  assert.equal(validScore(null), null);
});

test("parseLimit 預設 10 並限制在 1 到 50", () => {
  assert.equal(parseLimit(null), 10);
  assert.equal(parseLimit(""), 10);
  assert.equal(parseLimit("5"), 5);
  assert.equal(parseLimit("0"), 1);
  assert.equal(parseLimit("999"), 50);
});

test("parseLimit 拒絕非整數字串", () => {
  assert.equal(parseLimit("abc"), null);
  assert.equal(parseLimit("-1"), null);
  assert.equal(parseLimit("1.5"), null);
  assert.equal(parseLimit(" 5"), null);
});
