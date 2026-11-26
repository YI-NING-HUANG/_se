-- HW2 app1: 金大校務系統(選課核心) v1.0, 純標準函式庫 + sqlite3
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  password TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'student'
);
CREATE TABLE IF NOT EXISTS courses (
  id TEXT PRIMARY KEY,
  dept TEXT NOT NULL DEFAULT '',
  name TEXT NOT NULL,
  teacher TEXT NOT NULL DEFAULT '',
  credits INTEGER NOT NULL DEFAULT 3,
  capacity INTEGER NOT NULL DEFAULT 30,
  time_slot TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS enrollments (
  student_id TEXT NOT NULL,
  course_id TEXT NOT NULL,
  PRIMARY KEY (student_id, course_id)
);
