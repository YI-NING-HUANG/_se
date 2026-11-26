const express = require('express');
const cors = require('cors');
const { Pool } = require('pg');
const axios = require('axios');

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());

const pool = new Pool({
  host: process.env.DB_HOST || 'db',
  port: process.env.DB_PORT || 5432,
  user: process.env.DB_USER || 'hw6user',
  password: process.env.DB_PASSWORD || 'hw6pass',
  database: process.env.DB_NAME || 'hw6db',
});

const PYTHON_URL = process.env.PYTHON_URL || 'http://backend-python:5000';
const RUST_URL = process.env.RUST_URL || 'http://backend-rust:8000';

app.get('/api/health', (req, res) => {
  res.json({ service: 'node', status: 'ok', time: new Date().toISOString() });
});

// 聚合所有微服務狀態 + DB
app.get('/api/status', async (req, res) => {
  const result = {
    service: 'node',
    status: 'ok',
    time: new Date().toISOString(),
    dependencies: {}
  };
  // DB
  try {
    await pool.query('SELECT 1');
    result.dependencies.postgres = 'ok';
  } catch (e) {
    result.dependencies.postgres = 'error: ' + e.message;
  }
  // Python
  try {
    const r = await axios.get(`${PYTHON_URL}/api/health`, { timeout: 3000 });
    result.dependencies.python = r.data.status || 'ok';
  } catch (e) {
    result.dependencies.python = 'error: ' + e.message;
  }
  // Rust
  try {
    const r = await axios.get(`${RUST_URL}/api/health`, { timeout: 3000 });
    result.dependencies.rust = r.data.status || 'ok';
  } catch (e) {
    result.dependencies.rust = 'error: ' + e.message;
  }
  res.json(result);
});

app.get('/api/services', async (req, res) => {
  try {
    const r = await pool.query('SELECT * FROM services ORDER BY id');
    res.json(r.rows);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Notes CRUD (展示 Postgres)
app.get('/api/notes', async (req, res) => {
  try {
    const r = await pool.query('SELECT * FROM notes ORDER BY id DESC');
    res.json(r.rows);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post('/api/notes', async (req, res) => {
  const { content, author } = req.body;
  if (!content) return res.status(400).json({ error: 'content required' });
  try {
    const r = await pool.query(
      'INSERT INTO notes(content, author) VALUES($1, $2) RETURNING *',
      [content, author || 'web']
    );
    res.status(201).json(r.rows[0]);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.delete('/api/notes/:id', async (req, res) => {
  try {
    await pool.query('DELETE FROM notes WHERE id=$1', [req.params.id]);
    res.json({ deleted: req.params.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Node service listening on ${PORT}`);
});
