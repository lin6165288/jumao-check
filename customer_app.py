# customer_app.py
import streamlit as st
import pandas as pd
import mysql.connector

# —— 1. 数据库连接 —— (请改成你的真实连接信息)
conn = mysql.connector.connect(
    host     = "mysql-jumao.alwaysdata.net",
    user     = "jumao",
    password = "Ff1648955",
    database = "jumao_orders",
)


st.set_page_config(page_title="客戶訂單查詢", layout="centered")
st.title("🧡 橘貓代購｜客戶訂單查詢")

# —— 2. 客户输入姓名 —— 
name = st.text_input("請輸入您的姓名", "")

if st.button("🔎 查詢"):
    name = name.strip()
    if not name:
        st.warning("請先輸入您的姓名")
    else:
        # —— 3. 查询订单 —— 
        sql = """
        SELECT 
          order_time     AS 下單時間,
          platform       AS 平台,
          tracking_number AS 單號,
          amount_rmb     AS 金額(人民幣),
          is_arrived     AS 是否到貨,
          is_returned    AS 是否運回
        FROM orders
        WHERE customer_name LIKE %s
        ORDER BY order_time DESC
        """
        df = pd.read_sql(sql, conn, params=[f"%{name}%"])

        if df.empty:
            st.info("查無任何訂單，請確認您的姓名是否正確。")
        else:
            # —— 4. 格式化布林值 —— 
            df["是否到貨"]    = df["是否到貨"].map({True: "✔", False: "✘"})
            df["是否運回"]    = df["是否運回"].map({True: "✔", False: "✘"})
            df["下單時間"]    = pd.to_datetime(df["下單時間"]).dt.date

            # —— 5. 展示结果 —— 
            st.dataframe(df, use_container_width=True)
