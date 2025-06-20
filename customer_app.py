import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error

# 用 cache_resource 快取連線，Query 每次都重跑
@st.cache_resource
def get_connection():
    cfg = st.secrets["mysql"]
    return mysql.connector.connect(
        host=cfg["host"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
    )

st.set_page_config(page_title="客戶訂單查詢")
st.title("🧡 橘貓代購｜訂單查詢系統")

name = st.text_input("姓名")
if st.button("🔎 查詢"):
    if not name.strip():
        st.warning("請先輸入姓名")
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
            df = pd.read_sql(sql, conn, params=[f"%{name}%"])
            if df.empty:
                st.info("查無訂單，請確認姓名是否正確")
            else:
                st.dataframe(df, use_container_width=True)
        except Error as e:
            st.error(f"資料庫錯誤：{e}")
