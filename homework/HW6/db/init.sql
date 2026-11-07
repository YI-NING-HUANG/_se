CREATE TABLE IF NOT EXISTS services (
  id SERIAL PRIMARY KEY,
  name VARCHAR(50) NOT NULL,
  language VARCHAR(20) NOT NULL,
  description TEXT,
  port INT
);

CREATE TABLE IF NOT EXISTS notes (
  id SERIAL PRIMARY KEY,
  content TEXT NOT NULL,
  author VARCHAR(50) DEFAULT 'web',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO services (name, language, description, port) VALUES
('nginx', 'nginx', 'Web server + reverse proxy, 統一入口 :8080', 80),
('backend-node', 'Node.js', '主 API + Postgres CRUD + 聚合各服務狀態', 3000),
('backend-python', 'Python', 'Flask 運算服務: factorial / fibonacci', 5000),
('backend-rust', 'Rust', 'Axum 高效能服務: fib 計算', 8000),
('db', 'PostgreSQL', '關聯式資料庫: services, notes', 5432)
ON CONFLICT DO NOTHING;

INSERT INTO notes (content, author) VALUES
('Hello from HW6 microservices!', 'system'),
('試試新增一筆留言，資料會寫進 Postgres', 'system');
