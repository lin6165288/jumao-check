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

# === 查詢條件 ===
name = st.text_input("姓名（精準比對，英文大小寫不分）")
c1, c2 = st.columns(2)
with c1:
    only_arrived = st.checkbox("只看已到貨", value=False)
with c2:
    only_ready = st.checkbox("只看可運回（到貨且未運回）", value=False)

if st.button("🔎 查詢"):
    if not name.strip():
        st.warning("請先輸入姓名")
    else:
        try:
            conn = get_connection()

            # 動態 WHERE（精準姓名、大小寫不敏感）
            wheres = ["LOWER(TRIM(customer_name)) = LOWER(%s)"]
            params = [name.strip()]

            # 勾選快速濾器
            if only_arrived:
                wheres.append("is_arrived = 1")
            if only_ready:
                # 「可運回」＝已到貨且未運回（沿用你目前 is_returned 表示「是否運回」的設計）
                wheres.append("(is_arrived = 1 AND (is_returned = 0 OR is_returned IS NULL))")

            where_sql = " WHERE " + " AND ".join(wheres)

            # 主查詢（顯示給客人的表格）
            sql = f"""
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
                {where_sql}
                ORDER BY order_time DESC
            """
            df = pd.read_sql(sql, conn, params=params)

            # 統計「已到貨且未運回」數量與重量總和（不受勾選影響，統計永遠以此條件計）
            stat_sql = """
                SELECT
                  COUNT(*) AS cnt,
                  COALESCE(SUM(weight_kg), 0) AS total_weight
                FROM orders
                WHERE LOWER(TRIM(customer_name)) = LOWER(%s)
                  AND is_arrived = 1
                  AND (is_returned = 0 OR is_returned IS NULL)
            """
            stat = pd.read_sql(stat_sql, conn, params=[name.strip()]).iloc[0]
            conn.close()

            # 顯示統計卡片
            st.subheader("📦 已到貨且未運回（可運回）總覽")
            m1, m2 = st.columns(2)
            m1.metric("包裹數量", int(stat["cnt"]))
            m2.metric("重量總重（kg）", f"{float(stat['total_weight']):.2f}")

            # 顯示表格
            if df.empty:
                st.info("查無符合條件的訂單。")
            else:
                # 轉成 ✔️/❌，並處理 None
                df["是否到貨"] = df["是否到貨"].fillna(0).apply(lambda x: "✔️" if x else "❌")
                df["是否運回"] = df["是否運回"].fillna(0).apply(lambda x: "✔️" if x else "❌")
                st.dataframe(df, use_container_width=True)

        except Error as e:
            st.error(f"資料庫錯誤：{e}")
