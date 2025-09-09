# feedback_store.py  —— MySQL 版（共用）
import mysql.connector
from mysql.connector import Error
from contextlib import contextmanager

# 從 secrets 讀取同一組 MySQL 設定
import streamlit as st
db_cfg = st.secrets["mysql"]

@contextmanager
def _conn():
    conn = mysql.connector.connect(
        host=db_cfg["host"],
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["database"],
        autocommit=False,
    )
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    """確保表存在（安全可重複呼叫）"""
    sql = """
    CREATE TABLE IF NOT EXISTS feedbacks (
      id INT AUTO_INCREMENT PRIMARY KEY,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      content TEXT NOT NULL,
      user_agent VARCHAR(200),
      status ENUM('未處理','已讀','已回覆','忽略') DEFAULT '未處理',
      staff_note VARCHAR(255)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(sql)

def insert_feedback(content: str, contact: str | None, user_agent: str | None, session_hash: str | None):
    """參數簽名保留不動，前台現用的 contact / session_hash 可傳 None"""
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO feedbacks (content, user_agent) VALUES (%s, %s)",
                (content, (user_agent or None)[:200] if user_agent else None)
            )
            return cur.lastrowid

def read_feedbacks(keyword: str = "", status: str = "全部"):
    """回傳 list[dict]，後台直接丟進 pandas.DataFrame 即可"""
    where, params = [], []
    if keyword:
        where.append("(content LIKE %s OR staff_note LIKE %s)")
        kw = f"%{keyword}%"
        params += [kw, kw]
    if status != "全部":
        where.append("status = %s")
        params.append(status)
    sql = "SELECT id, created_at, content, user_agent, status, staff_note FROM feedbacks"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(sql, params)
            cols = ["id","created_at","content","user_agent","status","staff_note"]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

def update_status(ids: list[int], status: str, note: str | None = None):
    if not ids: return
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
