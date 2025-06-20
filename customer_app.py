# customer_app.py
import streamlit as st
import pandas as pd
import mysql.connector

st.set_page_config(page_title="客戶訂單查詢", layout="wide")
st.title("🔍 客戶訂單查詢")
st.write("請在下方輸入您的姓名，即可查詢所有訂單記錄")


#  建立資料庫連線
conn = mysql.connector.connect(
    host=st.secrets["mysql"]["host"],
    user=st.secrets["mysql"]["user"],
    password=st.secrets["mysql"]["password"],
    database=st.secrets["mysql"]["database"],
        )

# 2. 輸入姓名
name = st.text_input("姓名")

if st.button("🔎 查詢"):
    # 3. 用正確的表名：如果你已經把 order_6_20_version2 改名成 orders，就用 orders
    #    如果你想保留原名，就把下面的 `orders` 換回 `order_6_20_version2`
    sql = """
    SELECT
      order_time       AS 下單日期,
      platform         AS 平台,
      tracking_number  AS 單號,
      amount_rmb       AS 金額,
      is_arrived       AS 是否到貨,
      is_returned      AS 是否運回
    FROM `orders`
    WHERE customer_name LIKE %s
    ORDER BY order_time DESC
    """

    try:
        df = pd.read_sql(sql, conn, params=[f"%{name}%"])
    except Exception as e:
        st.error(f"📌 查詢過程發生錯誤：{e}")
    else:
        if df.empty:
            st.warning("⚠️ 查無任何訂單，請確認輸入的姓名是否正確。")
        else:
            st.dataframe(df)

# 程式結束後關掉連線
conn.close()
