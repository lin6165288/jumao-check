import streamlit as st
import mysql.connector
import pandas as pd

# 1. 頁面設定
st.set_page_config(page_title="🧡 橘貓代購｜客戶訂單查詢", layout="wide")
st.title("🔍 客戶訂單查詢")

st.markdown("""
請在下方輸入您的 **姓名**，即可查詢您所有的訂單紀錄
""")

# 2. 取得使用者輸入
name = st.text_input("姓名")

# 3. 非空輸入才執行查詢
if name.strip():
    try:
        # 4. 建立資料庫連線
        conn = mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"],
        )

        # 5. SQL 查詢（模糊匹配）
        sql = """
            SELECT
                order_time     AS 下單日期,
                platform       AS 平台,
                tracking_number AS 單號,
                amount_rmb     AS 金額,
                is_arrived     AS 是否到貨,
                is_returned    AS 是否運回
            FROM orders
            WHERE customer_name LIKE %s
            ORDER BY order_time DESC
        """
        params = (f"%{name.strip()}%",)

        # 6. 執行並讀取成 DataFrame
        df = pd.read_sql(sql, conn, params=params)

    except Exception as e:
        st.error(f"❌ 查詢過程發生錯誤：{e}")
        df = pd.DataFrame()  # 空的 DataFrame
    finally:
        conn.close()

    # 7. 顯示結果
    if df.empty:
        st.warning("⚠️ 查無任何訂單，請確認輸入的姓名是否正確。")
    else:
        st.success(f"共查詢到 {len(df)} 筆訂單")
        st.dataframe(df)

else:
    st.info("請先在上方輸入姓名，再按 Enter 即可查詢訂單。")
