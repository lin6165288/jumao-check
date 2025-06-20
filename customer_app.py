# customer_app.py
import streamlit as st
import mysql.connector
import pandas as pd

st.set_page_config(page_title="橘貓代購｜客戶訂單查詢", layout="wide")

# 1. 從 secrets.toml 取出資料庫設定
#    在 .streamlit/secrets.toml 裡面要長這樣：
# [mysql]
# host = "mysql-jumao.alwaysdata.net"
# user = "jumao"
# password = "Ff1648955"
# database = "jumao_orders"

@st.cache_data(show_spinner=False)
def get_connection():
    cfg = st.secrets["mysql"]
    conn = mysql.connector.connect(
        host=cfg["host"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
    )
    return conn

# 2. UI：標題與輸入
st.title("🧡 橘貓代購｜客戶訂單查詢系統")
st.write("請在下方輸入您的 **姓名**，即可查詢您所有的訂單記錄")

name = st.text_input("姓名", "")

if st.button("🔍 查詢"):
    if not name.strip():
        st.warning("請先輸入姓名！")
    else:
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
        try:
            df = pd.read_sql(sql, conn, params=[f"%{name}%"])
            conn.close()
        except Exception as e:
            st.error(f"查詢過程發生錯誤：{e}")
        else:
            if df.empty:
                st.info("查無任何訂單，請確認您輸入的姓名是否正確。")
            else:
                st.dataframe(df, use_container_width=True)
