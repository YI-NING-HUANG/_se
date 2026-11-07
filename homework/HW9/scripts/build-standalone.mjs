import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const apiBase = (
  process.env.DINO_API_BASE ||
  "https://hw9-dino-run.deciduous-device.workers.dev"
).replace(/\/+$/, "");

const [htmlSource, css, game, icon] = await Promise.all([
  readFile(path.join(root, "public/index.html"), "utf8"),
  readFile(path.join(root, "public/style.css"), "utf8"),
  readFile(path.join(root, "public/game.js"), "utf8"),
  readFile(path.join(root, "public/icon.svg"), "utf8"),
]);

const iconData = `data:image/svg+xml;base64,${Buffer.from(icon).toString("base64")}`;
const styleTag = `<style>\n${css}\n</style>`;
const configTag =
  `<script>\n` +
  `    window.DINO_STANDALONE = true;\n` +
  `    window.DINO_API_BASE = ${JSON.stringify(apiBase)};\n` +
  `  </script>\n` +
  `  <script>\n${game}\n  </script>`;

let output = htmlSource
  .replace(/[ \t]*<link rel="manifest"[^>]*>\r?\n/, "")
  .replace(/[ \t]*<link rel="stylesheet" href="\.\/style\.css">/, styleTag)
  .replace(/[ \t]*<script src="\.\/game\.js"><\/script>/, configTag)
  .replaceAll("./icon.svg", iconData);

if (output === htmlSource) {
  throw new Error("build-standalone: 找不到要內嵌的 HTML 區塊");
}
if (output.includes('src="./game.js"') || output.includes('href="./style.css"')) {
  throw new Error("build-standalone: 仍有未內嵌的外部資源");
}

output = `<!-- 由 scripts/build-standalone.mjs 產生；API: ${apiBase} -->\n${output}`;

await writeFile(path.join(root, "index.html"), output, "utf8");
console.log(`已產生 index.html（單檔版）`);
console.log(`排行榜 API：${apiBase}`);
