import streamlit as st
import pandas as pd
import mysql.connector

# 連接 MySQL（從 secrets 讀取）
conn = mysql.connector.connect(
    host=st.secrets["mysql"]["host"],
    user=st.secrets["mysql"]["user"],
    password=st.secrets["mysql"]["password"],
    database=st.secrets["mysql"]["database"]
)
cursor = conn.cursor(dictionary=True)

st.set_page_config(page_title="橘貓代購貨況查詢系統")
st.title("🐾 橘貓代購貨況查詢系統")

# 使用者輸入姓名
name = st.text_input("請輸入姓名查詢")

if name:
    query = "SELECT order_time, platform, amount_rmb, is_arrived, is_returned FROM orders WHERE customer_name LIKE %s"
    cursor.execute(query, (f"%{name}%",))
    rows = cursor.fetchall()
    
    if rows:
        df = pd.DataFrame(rows)
        df["is_arrived"] = df["is_arrived"].apply(lambda x: "✔" if x else "✘")
        df["is_returned"] = df["is_returned"].apply(lambda x: "✔" if x else "✘")
        df.columns = ["下單日期", "平台", "金額（人民幣）", "是否到貨", "是否已運回"]
        st.dataframe(df)
    else:
        st.info("查無資料，請確認姓名是否輸入正確")
