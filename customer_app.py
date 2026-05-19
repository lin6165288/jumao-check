import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error

# 🔸 匿名回饋（MySQL 小表）
from feedback_store import init_db, insert_feedback

st.set_page_config(page_title=" 橘貓代購｜訂單查詢 & 匿名回饋", page_icon="🧡", layout="centered")

# 初始化回饋表（不存在就建立）
init_db()

# ===== 你的 MySQL（訂單）連線 =====
db_cfg = st.secrets["mysql"]
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        port=int(st.secrets["mysql"]["port"]),
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        charset="utf8mb4",
        connection_timeout=10,
    )

# ===== 訂單查詢頁 =====
def get_last_update_time():
    try:
        conn = get_connection()
        sql = """
            SELECT MAX(order_time) AS last_update
            FROM orders
        """
        df = pd.read_sql(sql, conn)
        conn.close()

        last_update = df.loc[0, "last_update"]

        if pd.isna(last_update):
            return "目前尚無訂單資料"

        return pd.to_datetime(last_update).strftime("%Y/%m/%d")

    except Exception:
        return "讀取失敗"



def page_orders():
    st.title("🧡 橘貓代購｜訂單查詢系統")
    
    last_update_time = get_last_update_time()
    st.caption(f"🕒 資料目前更新至：{last_update_time}")

    name = st.text_input("請輸入登記包裹用名稱(默認LINE名稱)", key="q_name")
    only_incomplete = st.checkbox("只看未完成訂單（未運回）", value=False, key="q_only_incomplete")

    if st.button("🔎 查詢", key="q_search_btn"):
        if not name.strip():
            st.warning("請先輸入姓名")
        else:
            try:
                conn = get_connection()

                wheres = ["LOWER(TRIM(customer_name)) = LOWER(%s)"]
                params = [name.strip()]
                if only_incomplete:
                    wheres.append("(is_returned = 0 OR is_returned IS NULL)")
                where_sql = " WHERE " + " AND ".join(wheres)

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

                st.subheader("📦 已到倉包裹總計")
                m1, m2 = st.columns(2)
                m1.metric("包裹數量", int(stat["cnt"]))
                m2.metric("重量總重（kg）", f"{float(stat['total_weight']):.2f}")

                if df.empty:
                    st.info("查無符合條件的訂單。")
                else:
                    df["是否到貨"] = df["是否到貨"].fillna(0).apply(lambda x: "✔️" if x else "❌")
                    df["是否運回"] = df["是否運回"].fillna(0).apply(lambda x: "✔️" if x else "❌")
                    st.dataframe(df, use_container_width=True)

            except Error as e:
                st.error(f"資料庫錯誤：{e}")

# ===== 匿名回饋頁（無聯絡方式/驗證/頻率限制）=====
def page_feedback():
    st.title("📮 匿名回饋 ")

    st.info(" **有任何想法、建議，或希望看到的新功能嗎？** \n🧡 請放心留下訊息，我們都會認真參考！", icon="😺")

    # --- 先處理上一輪的旗標（讓成功提示與清空在 rerun 後發生）---
    flash_msg = st.session_state.pop("fb_flash", None)
    if flash_msg:
        st.success(flash_msg)
    if st.session_state.pop("fb_clear", False):
        st.session_state.pop("fb_content", None)

    content = st.text_area("寫下你想對橘貓說的話（匿名）", height=200, key="fb_content")

    if st.button("送出回饋", type="primary", key="fb_submit_btn"):
        if not content.strip():
            st.error("請先填寫回饋內容。")
        else:
            try:
                insert_feedback(content.strip())  # 多餘參數可省略
                st.session_state["fb_flash"] = "已收到，謝謝你的回饋！🧡"
                st.session_state["fb_clear"] = True
                st.rerun()
            except Exception as e:
                st.error(f"寫入失敗：{e}")

# ===== 導覽 =====
page = st.sidebar.radio("功能選單", ["🔎 訂單查詢", "📮 匿名回饋"], index=0, key="nav_radio")
page_orders() if page == "🔎 訂單查詢" else page_feedback()

# ===== FAQ =====
st.divider()
with st.expander("📘 常見問題（QA）", expanded=False):
    st.markdown("""
### 查詢與顯示
**Q1：找不到我的訂單？**  
A：請確認輸入的名稱與下單截圖上名稱完全一致。若仍找不到，可能尚未建檔或資料有誤，請截圖本頁並私訊橘貓協助。

**Q2：資料多久更新一次？**  
A：系統 1~2 日同步一次；遇到高峰期或系統維護，可能延後幾日，若一直未更新，請私訊橘貓協助。

**Q3：怎麼只看未完成的訂單？**  
A：勾選「只看未完成訂單（未運回）」即可，只會顯示尚未運回的包裹。

### 狀態與時程
**Q4：「已到貨」代表什麼？**  
A：包裹已抵達大陸集運倉，可以安排運回。

**Q5：多久會安排運回？**  
A：通常為【每週日】集中運回；詳細運回批次可查看【當月船班】，臨時異動會另行公告。

**Q6：到貨後多久會通知？**  
A：到貨不會另外通知。默認所有包裹都到貨後運回，若有需要提前運回可私訊橘貓。

### 費用與重量
**Q7：重量怎麼計算？**  
A：以【包裹實重】為準；若多件包裹會合併計算。實際費用以橘貓給你的明細為準。

**Q8：可以合併多件一起運回嗎？**  
A：可以，我們會在同一批次盡量合併；如需分批或加急請先告知橘貓。
""")


