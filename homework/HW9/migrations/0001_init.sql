-- DINO RUN 全球排行榜：Cloudflare D1（SQLite）初始結構
CREATE TABLE IF NOT EXISTS scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  score INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scores_rank ON scores (score DESC, id ASC);
