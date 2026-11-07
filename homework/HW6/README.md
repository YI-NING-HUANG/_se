# HW6 Docker 微服務系統

以 Docker Compose 建置的迷你微服務系統：**nginx 統一入口 + Node.js + Python + Rust + PostgreSQL**，
附一個可直接操作的 Web 介面，用來展示服務狀態、資料庫 CRUD 與各後端服務。

---

## 1. 學習目標與 Docker 核心概念

| 概念 | 說明 | 本專案對應 |
|---|---|---|
| Image（映像） | 唯讀的執行環境模板，由 Dockerfile 建置 | `hw6-backend-node`、`hw6-backend-rust` 等 |
| Container（容器） | 由映像啟動的執行實體，彼此隔離 | `hw6-node`、`hw6-db`、`hw6-nginx` … |
| Volume（資料卷） | 容器外的持久化儲存 | `pgdata` → `/var/lib/postgresql/data` |
| Bind Mount | 把主機檔案掛進容器 | `./db/init.sql` → `docker-entrypoint-initdb.d/` |
| Network（網路） | 容器間的通訊網路，可用服務名稱當 DNS | Compose 預設網路，`db`、`backend-python`… |
| Dockerfile | 描述如何建置映像的指令檔 | 4 個自建映像 + 1 個官方映像 |
| Docker Compose | 用 YAML 編排多容器系統 | `docker-compose.yml`（5 個服務） |
| Reverse Proxy | 反向代理，統一對外入口並轉發請求 | nginx 依路徑轉發到三個後端 |
| Multi-stage Build | 多階段建置，只保留執行期需要的產物 | Rust 以 `rust:1.82` 編譯、`debian` 執行 |

---

## 2. 系統架構

```
                     Browser
                        │  http://localhost:8080
                        ▼
              ┌──────────────────┐
              │      nginx       │  web server + reverse proxy
              │   (nginx:alpine) │
              └────────┬─────────┘
                       │ Compose 內部網路（服務名稱即 DNS）
       ┌───────────────┼────────────────┬─────────────────┐
       │               │                │                 │
       ▼               ▼                ▼                 ▼
   / 靜態頁面      /api/*           /python/*          /rust/*
 frontend/      backend-node       backend-python     backend-rust
 index.html        :3000              :5000              :8000
                    │                                     │
                    ▼                                     │
              ┌───────────┐                               │
              │    db     │  PostgreSQL 16                │
              │  :5432    │  services / notes             │
              └───────────┘                               │
                    ▲                                     │
                    └──── backend-node 聚合查詢各服務 ────┘
```

對外只開放 nginx 的 `8080`，其餘服務僅在 Compose 內部網路互通。

---

## 3. 專案結構

```
HW6/
├── docker-compose.yml          # 5 個服務的編排定義
├── README.md                   # 本文件（學習與操作記錄）
├── .dockerignore               # 避免把不必要的檔案送進 build context
├── db/
│   └── init.sql                # 資料庫初始化：services、notes 兩張表 + 種子資料
├── nginx/
│   ├── Dockerfile              # 打包 nginx.conf 與前端靜態頁
│   └── nginx.conf              # 靜態網頁 + 反向代理設定
├── frontend/
│   └── index.html              # 簡易 Web 展示介面（純 HTML/JS）
├── backend-node/
│   ├── Dockerfile
│   ├── package.json
│   └── server.js               # 主 API：health/status、notes CRUD、services
├── backend-python/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py                  # Flask：health/info/compute（factorial、fibonacci）
└── backend-rust/
    ├── Dockerfile              # 多階段建置
    ├── Cargo.toml
    └── src/main.rs             # Axum：health/hello/fib
```

---

## 4. 服務一覽

| 服務 | 映像 / 語言 | 功能 | 對外路徑 |
|---|---|---|---|
| nginx | `nginx:alpine`（自建 Dockerfile） | Web server + Reverse Proxy | `http://localhost:8080/` |
| backend-node | `node:20-alpine`（自建） | 主 API、聚合狀態、Notes CRUD | `/api/health`、`/api/status`、`/api/notes`、`/api/services` |
| backend-python | `python:3.12-slim`（自建） | Flask 運算服務 | `/python/api/health`、`/python/api/info`、`/python/api/compute` |
| backend-rust | `rust:1.82-slim-bookworm` → `debian:bookworm-slim`（自建、多階段） | Axum 高效能 fib 服務 | `/rust/api/health`、`/rust/api/hello`、`/rust/api/fib?n=30` |
| db | `postgres:16-alpine`（官方） | 關聯式資料庫 | 僅內部 `db:5432` |

---

## 5. Dockerfile 重點說明

### backend-node
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --production
COPY server.js ./
EXPOSE 3000
CMD ["node", "server.js"]
```
先複製 `package.json` 再安裝依賴，最後才複製程式碼，可有效利用 **layer cache**：只改程式碼時不會重跑 `npm install`。

### backend-python
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
EXPOSE 5000
CMD ["python", "app.py"]
```
`--no-cache-dir` 可縮小映像；同樣把依賴安裝與程式碼分層。

### backend-rust（Multi-stage Build）
```dockerfile
FROM rust:1.82-slim-bookworm AS builder
WORKDIR /app
COPY Cargo.toml ./
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/hw6-backend-rust /app/server
EXPOSE 8000
CMD ["/app/server"]
```
第一階段用完整 Rust 工具鏈編譯；第二階段只複製 release binary，執行映像不需要編譯器，體積大幅縮小。

### nginx
```dockerfile
FROM nginx:alpine
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY frontend /usr/share/nginx/html
EXPOSE 80
```
把反向代理設定與靜態前端一起打包進映像。

### Nginx 反向代理關鍵設定
```nginx
location /api/    { proxy_pass http://node_api/api/; }
location /python/ { proxy_pass http://python_api/; }
location /rust/   { proxy_pass http://rust_api/; }
```
- `proxy_pass` 結尾有 `/` 時會**去掉 location 前綴**，所以 `/python/api/health` → 後端收到 `/api/health`。
- Node 的 `proxy_pass http://node_api/api/;` 會保留 `/api` 前綴。
- `upstream` 直接使用 Compose 服務名稱（`backend-node`、`backend-python`、`backend-rust`），由 Docker 內部 DNS 解析。

---

## 6. docker-compose.yml 重點說明

- **services**：`db`、`backend-node`、`backend-python`、`backend-rust`、`nginx` 共 5 個。
- **build**：四個服務各自用目錄下的 Dockerfile 建置；nginx 的 context 是專案根目錄，才能同時複製 `nginx/` 與 `frontend/`。
- **ports**：只有 nginx 映射 `8080:80`（host:container）；其他服務用 `expose` 僅對內部網路開放。
- **depends_on + condition**：Node 會等 PostgreSQL 的 `healthcheck` 通過後才啟動：
  ```yaml
  depends_on:
    db:
      condition: service_healthy
  ```
- **healthcheck**：以 `pg_isready -U hw6user -d hw6db` 判斷資料庫是否就緒。
- **volumes**：
  - `pgdata`（named volume）：資料庫資料持久化，`docker compose down` 不會刪除。
  - `./db/init.sql`（bind mount）：第一次建立資料庫時自動執行初始化 SQL。
- **環境變數**：Node 透過 `DB_HOST=db` 等變數連線；服務名稱就是主機名稱。

> 注意：`init.sql` 只會在 **`pgdata` 首次初始化** 時執行。若修改 SQL，需 `docker compose down -v` 清掉資料卷後重建。

---

## 7. 操作記錄（實際執行過的指令）

### 7.1 環境檢查
```bash
docker --version
# Docker version 29.8.2

docker compose version
# Docker Compose version v5.6.0
```
Windows 上需先啟動 Docker Desktop，daemon 沒起來時會出現：
`failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`

### 7.2 建置與啟動
```bash
docker compose up -d --build
```
首次建置會下載基底映像並編譯 Rust（最久）。完成後：
```bash
docker compose ps
```
實際結果：
```
NAME         SERVICE          STATUS                    PORTS
hw6-db       db               Up (healthy)              5432/tcp
hw6-nginx    nginx            Up                        0.0.0.0:8080->80/tcp
hw6-node     backend-node     Up                        3000/tcp
hw6-python   backend-python   Up                        5000/tcp
hw6-rust     backend-rust     Up                        8000/tcp
```

### 7.3 驗證 API（實際輸出）
```bash
curl http://localhost:8080/nginx-health
# nginx ok

curl http://localhost:8080/api/status
# {"service":"node","status":"ok",
#  "dependencies":{"postgres":"ok","python":"ok","rust":"ok"}}

curl http://localhost:8080/python/api/health
# {"service":"python","status":"ok",...}

curl http://localhost:8080/rust/api/health
# {"service":"rust","status":"ok",...}
```

```bash
curl -X POST http://localhost:8080/api/notes \
  -H "Content-Type: application/json" \
  -d '{"content":"docker compose verification","author":"tester"}'
# {"id":3,"content":"docker compose verification","author":"tester",...}

curl -X POST http://localhost:8080/python/api/compute \
  -H "Content-Type: application/json" -d '{"n":10}'
# {"factorial":"3628800","fibonacci":55,"n":10,"service":"python"}

curl "http://localhost:8080/rust/api/fib?n=30"
# {"service":"rust","n":30,"fibonacci":832040,"time_ms":0}

curl -X DELETE http://localhost:8080/api/notes/3
# {"deleted":"3"}
```

### 7.4 常用維運指令
```bash
docker compose logs -f              # 追蹤所有服務日誌
docker compose logs -f backend-node # 只看 Node 日誌
docker compose restart nginx        # 重啟單一服務
docker compose exec db psql -U hw6user -d hw6db -c "SELECT * FROM notes;"
docker compose exec backend-node sh # 進入容器
docker compose down                 # 停止並移除容器（保留資料）
docker compose down -v              # 連同 pgdata 資料卷一起刪除
docker compose images               # 查看本專案建置的映像
docker image prune -f               # 清理未使用的映像層
```

---

## 8. Web 展示介面

開啟 <http://localhost:8080/> 可以看到：

- 系統架構圖
- 各服務即時健康狀態（nginx / node / python / rust），資料由 `/api/status` 聚合
- PostgreSQL 留言板：新增、刪除留言（經 Node API 寫入 DB）
- Python 運算：factorial + fibonacci
- Rust 高速 fib 計算
- 服務清單（從 `services` 資料表讀取）

整頁只透過 nginx 的 `8080` 對外，前端 fetch 的相对路徑會自動被反向代理到對應微服務。

---

## 9. 遇到的問題與解決記錄

| 問題 | 原因 | 解決方式 |
|---|---|---|
| `failed to connect to the docker API ...` | Docker Desktop daemon 未啟動 | 先啟動 Docker Desktop，等 `docker info` 有回應 |
| `net/http: timeout awaiting response headers`（建置時） | Docker Hub 連線慢／逾時 | 先個別 `docker pull` 基底映像，再重跑 `docker compose up --build` |
| `short read: expected ... bytes but got ...: unexpected EOF` | 拉取 `rust:1.82-slim-bookworm` 網路中斷 | 重新 `docker pull`，成功後再建置 |
| Rust 建置很久 | 首次需下載 crates 並完整編譯 | 多階段建置縮小執行映像；後續可善用 layer cache |
| 修改 `db/init.sql` 後沒生效 | PostgreSQL 只在資料卷第一次初始化時執行 init script | `docker compose down -v` 後重新啟動 |
| `proxy_pass` 路徑前綴不符 | 結尾有無 `/` 會改變轉發路徑 | `/python/`、`/rust/` 結尾加 `/` 去掉前綴；`/api/` 保留前綴 |
| 8080 連接埠被占用 | 主機已有其他程式使用 | 修改 compose 的 `"8080:80"` 為其他埠，例如 `"8090:80"` |

---

## 10. 學習心得

1. **Dockerfile 的分層順序會直接影響建置速度**：把變動頻率低的依賴安裝放前面、程式碼放後面，才能吃到 cache。
2. **Compose 讓多容器協作變得可宣告、可重現**：服務名稱即 DNS、`depends_on` + healthcheck 解決啟動順序、named volume 解決資料持久化。
3. **反向代理是微服務對外的統一窗口**：瀏覽器只需要知道一個位址，內部服務完全不需暴露到主機，安全性與管理都更好。
4. **多階段建置對編譯型語言非常重要**：Rust 映像從「完整工具鏈」縮減為「執行檔 + 最小基底」，部署更輕量。
5. **容器是拋棄式的，資料要放在 volume**：重建容器不會影響 `pgdata`，但這也代表初始化 SQL 只跑一次，除錯時要記得資料卷的存在。

---

## 11. 繳交內容檢查清單

- [x] `docker-compose.yml`：nginx、PostgreSQL、Node.js、Python、Rust 共 5 個服務
- [x] 各服務 `Dockerfile`（Node / Python / Rust / nginx）
- [x] nginx 作為 web server 與 reverse proxy
- [x] PostgreSQL 資料庫與初始化 SQL
- [x] Node.js、Python、Rust 三種開發執行環境
- [x] 簡易 Web 介面展示整體系統
- [x] README.md：架構、操作指令、驗證結果與學習記錄
