import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error

# 1. 從 Streamlit secrets 讀取資料庫設定
#    secrets.toml 範例放在 .streamlit/secrets.toml 裡：
#
# [mysql]
# host     = "mysql-jumao.alwaysdata.net"
# user     = "jumao"
# password = "Ff1648955"
# database = "jumao_orders"

db_cfg = st.secrets["mysql"]

@st.cache_data(show_spinner=False)
def get_connection():
    """建立並回傳一個新的 MySQL 連線"""
    return mysql.connector.connect(
        host=db_cfg["host"],
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["database"],
    )

# ===== Streamlit 介面設定 =====
st.set_page_config(page_title="🧡 橘貓代購｜客戶訂單查詢", layout="centered")
st.title("🧡 橘貓代購｜客戶訂單查詢系統")
st.write("請在下方輸入您的 **姓名**，即可查詢所有的訂單紀錄")

# 使用者輸入姓名
name = st.text_input("姓名", "")

# 查詢按鈕
if st.button("🔎 查詢"):
    name = name.strip()
    if not name:
        st.warning("⚠️ 請先輸入姓名")
    else:
        try:
            conn = get_connection()
            sql = """
                SELECT
                  order_time      AS 下單日期,
                  platform        AS 平台,
                  tracking_number AS 單號,
                  amount_rmb      AS 金額,
                  is_arrived      AS 是否到貨,
                  is_returned     AS 是否運回
                FROM orders
                WHERE customer_name LIKE %s
                ORDER BY order_time DESC
            """
            # 用 pandas 直接跑 SQL
            df = pd.read_sql(sql, conn, params=[f"%{name}%"])
            conn.close()

            if df.empty:
                st.info("ℹ️ 查無任何訂單，請確認您的姓名是否正確。")
            else:
                st.dataframe(df, use_container_width=True)

        except Error as e:
            st.error(f"❌ 查詢過程發生錯誤：{e}")
