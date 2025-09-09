# feedback_store.py
import os, sqlite3
from contextlib import closing

# 將 DB 放在專案的 data/ 資料夾
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "feedbacks.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS feedbacks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT DEFAULT (datetime('now','localtime')),
  content TEXT NOT NULL,
  contact TEXT,
  user_agent TEXT,
  session_hash TEXT,
  status TEXT DEFAULT '未處理',
  staff_note TEXT
);
"""

def _conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with closing(_conn()) as con:
        con.execute(SCHEMA_SQL)
        con.commit()

def insert_feedback(content: str, contact: str | None, user_agent: str | None, session_hash: str | None):
    with closing(_conn()) as con:
        con.execute(
            "INSERT INTO feedbacks (content, contact, user_agent, session_hash) VALUES (?,?,?,?)",
            (content, contact, user_agent, session_hash)
        )
        con.commit()

def read_feedbacks(keyword: str = "", status: str = "全部"):
    sql = "SELECT id, created_at, content, contact, status, staff_note FROM feedbacks"
    params = []
    where = []
    if keyword:
        where.append("(content LIKE ? OR contact LIKE ?)")
        params += [f"%{keyword}%", f"%{keyword}%"]
    if status != "全部":
        where.append("status=?")
        params.append(status)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    with closing(_conn()) as con:
        cur = con.execute(sql, params)
        rows = cur.fetchall()
    # 回傳成簡單的 list[dict]
    cols = ["id", "created_at", "content", "contact", "status", "staff_note"]
    return [dict(zip(cols, r)) for r in rows]

def update_status(ids: list[int], status: str, note: str | None = None):
    if not ids:
        return
    with closing(_conn()) as con:
        if note is None:
            con.executemany("UPDATE feedbacks SET status=? WHERE id=?", [(status, i) for i in ids])
        else:
            con.executemany("UPDATE feedbacks SET status=?, staff_note=? WHERE id=?", [(status, note, i) for i in ids])
        con.commit()
