import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error

db_cfg = st.secrets["mysql"]

def get_connection():
    return mysql.connector.connect(
        host=db_cfg["host"],
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["database"],
    )

st.set_page_config(page_title="橘貓代購｜訂單查詢系統")
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
                  order_id        AS 訂單編號,
                  order_time      AS 下單日期,
                  platform        AS 平台,
                  tracking_number AS 單號,
                  amount_rmb      AS 金額,
                  weight_kg       AS 包裹重量,
                  is_arrived      AS 是否到貨,
                  is_returned     AS 是否運回
                FROM orders
                WHERE customer_name LIKE %s
                  AND is_returned = 0         -- 只選擇「未運回」的訂單
                ORDER BY order_time DESC
            """
            df = pd.read_sql(sql, conn, params=[f"%{name}%"])
            conn.close()

            if df.empty:
                st.info("查無符合條件的訂單，若您已取貨請聯絡客服。")
            else:
                # 轉成 ✔️/❌
                df["是否到貨"] = df["是否到貨"].apply(lambda x: "✔️" if x else "❌")
                df["是否運回"] = df["是否運回"].apply(lambda x: "✔️" if x else "❌")
                st.dataframe(df, use_container_width=True)

        except Error as e:
            st.error(f"資料庫錯誤：{e}")
