# feedback_store.py —— 簡化版（只存 content）
import mysql.connector
from mysql.connector import Error
from contextlib import contextmanager
import streamlit as st

# 共用 MySQL 連線設定（沿用你現有的 st.secrets["mysql"]）
db_cfg = st.secrets["mysql"]

@contextmanager
def _conn():
    conn = mysql.connector.connect(
        host=db_cfg["host"],
        port=int(db_cfg.get("port", 3306)),
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["database"],
        autocommit=False,
        charset="utf8mb4",
        connection_timeout=10,
    )
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    """建立 feedbacks 表（若不存在）"""
    sql = """
    CREATE TABLE IF NOT EXISTS feedbacks (
      id INT AUTO_INCREMENT PRIMARY KEY,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      content TEXT NOT NULL,
      status ENUM('未處理','已讀','已回覆','忽略') DEFAULT '未處理',
      staff_note VARCHAR(255)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(sql)

def insert_feedback(content: str, contact: str | None = None, user_agent: str | None = None, session_hash: str | None = None):
    """為了相容舊呼叫簽名，保留多餘參數，但實際只存 content。回傳 row id。"""
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute("INSERT INTO feedbacks (content) VALUES (%s)", (content,))
            return cur.lastrowid

def read_feedbacks(keyword: str = "", status: str = "全部"):
    """讀取回饋清單，回傳 list[dict]"""
    where, params = [], []
    if keyword:
        where.append("(content LIKE %s OR staff_note LIKE %s)")
        kw = f"%{keyword}%"
        params += [kw, kw]
    if status != "全部":
        where.append("status = %s")
        params.append(status)
    sql = "SELECT id, created_at, content, status, staff_note FROM feedbacks"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(sql, params)
            cols = ["id","created_at","content","status","staff_note"]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

def update_status(ids: list[int], status: str, note: str | None = None):
    """更新狀態／備註"""
    if not ids:
        return
    ph = ",".join(["%s"] * len(ids))
    params = [status]
    set_note = ""
    if note is not None:
        set_note = ", staff_note = %s"
        params.append(note)
    sql = f"UPDATE feedbacks SET status = %s{set_note} WHERE id IN ({ph})"
    params += ids
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(sql, params)
