import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error

# ====== 資料庫連線設定 ======
DB_CONFIG = {
    "host": "mysql-jumao.alwaysdata.net",
    "user": "jumao",
    "password": "Ff1648955",  # ← 把 YOUR_PASSWORD_HERE 換成你的密碼
    "database": "jumao_orders"
}

def get_connection():
    """建立並回傳一個新的 MySQL 連線"""
    return mysql.connector.connect(**DB_CONFIG)

# ====== Streamlit 介面 ======
st.set_page_config(page_title="客戶訂單查詢", layout="centered")
st.title("🔍 客戶訂單查詢")
st.write("請在下方輸入您的 **姓名**，即可查詢所有的訂單紀錄")

# 輸入欄位
name = st.text_input("姓名", "")

# 按鈕觸發查詢
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
                FROM orders_new
                WHERE customer_name LIKE %s
                ORDER BY order_time DESC
            """
            # 執行查詢
            df = pd.read_sql(sql, conn, params=[f"%{name}%"])
            conn.close()

            if df.empty:
                st.info("ℹ️ 查無任何訂單，請確認您的姓名是否正確。")
            else:
                st.dataframe(df)
        except Error as e:
            st.error(f"❌ 查詢過程發生錯誤：{e}")
