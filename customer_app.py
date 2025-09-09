import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error
import time, random, hashlib

# SQLite 側車檔：匿名回饋儲存
from feedback_store import init_db, insert_feedback, DB_PATH

# ===== 基本設定 =====
st.set_page_config(page_title=" 橘貓代購｜訂單查詢 & 回饋", page_icon="🧡", layout="centered")

# 初始化側車 DB（第一次會自動建表）
init_db()

# ===== MySQL 連線（維持你原本的查單資料來源）=====
db_cfg = st.secrets["mysql"]

def get_connection():
    return mysql.connector.connect(
        host=db_cfg["host"],
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["database"],
    )

# ===== 查單頁 =====
def page_orders():
    st.title("🧡 橘貓代購｜訂單查詢系統")

    # ▶ 加唯一 key，避免與其他頁面重複
    name = st.text_input("請輸入登記包裹用名稱(默認LINE名稱)", key="q_name")

    # ✅ 單一濾器：只看未完成（＝未運回）
    only_incomplete = st.checkbox("只看未完成訂單（未運回）", value=False, key="q_only_incomplete")

    if st.button("🔎 查詢", key="q_search_btn"):
        if not name.strip():
            st.warning("請先輸入姓名")
        else:
            try:
                conn = get_connection()

                # 精準姓名、大小寫不敏感
                wheres = ["LOWER(TRIM(customer_name)) = LOWER(%s)"]
                params = [name.strip()]

                # 只看未完成＝未運回（is_returned=0 or NULL）
                if only_incomplete:
                    wheres.append("(is_returned = 0 OR is_returned IS NULL)")

                where_sql = " WHERE " + " AND ".join(wheres)

                # 主查詢
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

                # 「已到貨且未運回」統計（固定口徑，不受上方勾選影響）
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

                # 統計卡片
                st.subheader("📦 已到倉包裹總計")
                m1, m2 = st.columns(2)
                m1.metric("包裹數量", int(stat["cnt"]))
                m2.metric("重量總重（kg）", f"{float(stat['total_weight']):.2f}")

                # 結果表格
                if df.empty:
                    st.info("查無符合條件的訂單。")
                else:
                    df["是否到貨"] = df["是否到貨"].fillna(0).apply(lambda x: "✔️" if x else "❌")
                    df["是否運回"] = df["是否運回"].fillna(0).apply(lambda x: "✔️" if x else "❌")
                    st.dataframe(df, use_container_width=True)

            except Error as e:
                st.error(f"資料庫錯誤：{e}")

# ===== 匿名回饋頁（SQLite 側車檔，不動 MySQL 結構）=====
def page_feedback():
    st.title("📮 匿名回饋 ")

    # 美化提示
    st.info("💡 **若有任何建議，或期待我們推出的新功能，歡迎在此留言** 🧡\n您的聲音將幫助橘貓代購越來越好！", icon="😺")

    # ===== 1) 先處理「上一輪」留下的旗標（顯示成功訊息、清空內容）=====
    # 顯示上一次送出後要顯示的訊息
    flash_msg = st.session_state.pop("fb_flash", None)
    if flash_msg:
        st.success(flash_msg)

    # 清空輸入內容（要在建立 widget 之前做）
    if st.session_state.pop("fb_clear", False):
        # 用 pop 把 key 移除，讓下一個 text_area 以預設值重新建立
        st.session_state.pop("fb_content", None)

    # ===== 2) 渲染輸入元件 =====
    content = st.text_area("寫下你想對橘貓說的話（匿名）", height=200, key="fb_content")

    # ===== 3) 送出 =====
    if st.button("送出回饋", type="primary", key="fb_submit_btn"):
        if not content.strip():
            st.error("請先填寫回饋內容。")
        else:
            try:
                ua = st.session_state.get("user_agent", "unknown")
                # session_hash 不需要，傳 None
                from feedback_store import insert_feedback  # 保險起見，若你已在檔頭 import 可移除此行
                insert_feedback(content.strip(), None, str(ua)[:200], None)

                # 設定「下一輪」要做的事：顯示成功訊息 + 清空輸入
                st.session_state["fb_flash"] = "已收到，謝謝你的回饋！🧡"
                st.session_state["fb_clear"] = True

                # 重新執行一次，讓上面旗標生效（不會出現黃色警告，因為不在 callback 內再 rerun）
                st.rerun()
            except Exception as e:
                st.error(f"寫入失敗：{e}")


# ===== 導覽（同一連結切換）=====
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









