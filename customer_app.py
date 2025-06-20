import streamlit as st
import pandas as pd
import mysql.connector

st.title("🔍 客戶訂單查詢")


# 4. 建立資料庫連線
conn = mysql.connector.connect(
    host=st.secrets["mysql"]["host"],
    user=st.secrets["mysql"]["user"],
    password=st.secrets["mysql"]["password"],
    database=st.secrets["mysql"]["database"],
    )

st.write("▶▶▶ 目前查的表是 orders_new")  
st.code(sql)

name = st.text_input("姓名")
if st.button("查詢"):
    sql = """
    SELECT
      `order_time`       AS 下單日期,
      `platform`         AS 平台,
      `tracking_number`  AS 單號,
      `amount_rmb`       AS 金額,
      `is_arrived`       AS 是否到貨,
      `is_returned`      AS 是否運回
    FROM `orders_new`
    WHERE `customer_name` LIKE %s
    ORDER BY `order_time` DESC
    """
    try:
        df = pd.read_sql(sql, conn, params=[f"%{name}%"])
        if df.empty:
            st.warning("⚠️ 查無訂單，請確認姓名是否正確。")
        else:
            st.dataframe(df)
    except Exception as e:
        st.error(f"查詢出錯：{e}")
    finally:
        conn.close()
