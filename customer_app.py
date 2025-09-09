import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error
import time, random, hashlib
from feedback_store import init_db, insert_feedback


init_db()

#
# 把原本查詢頁包成函式（原始程式整段貼進去，不改內容）
def page_orders():
    st.title("🧡 橘貓代購｜訂單查詢系統")
    name = st.text_input("請輸入登記包裹用名稱(默認LINE名稱)")
    # ✅ 單一濾器：只看未完成（＝未運回）
    only_incomplete = st.checkbox("只看未完成訂單（未運回）", value=False)

    if st.button("🔎 查詢"):
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
        # ... 你原本的查詢 UI + SQL 全部在這裡 ...



def page_feedback():
    st.title("📮 匿名回饋 ")
    st.info("匿名聲明：不要求登入、不主動蒐集 IP。為防洗版，僅在本機建立一次性雜湊碼做頻率限制（不可逆）。", icon="🕊️")

    if "fb_session_hash" not in st.session_state:
        raw = f"{time.time()}-{random.random()}"
        st.session_state.fb_session_hash = hashlib.sha256(raw.encode()).hexdigest()
    if "fb_last_ts" not in st.session_state:
        st.session_state.fb_last_ts = 0.0

    content = st.text_area("寫下你想對橘貓說的話（匿名）", height=200)
    contact = st.text_input("聯絡方式（選填，LINE／Email）", value="")

    a, b = random.randint(1,9), random.randint(1,9)
    st.write(f"驗證題：{a} + {b} = ?")
    ans = st.number_input("請輸入答案", step=1, format="%d")
    agree = st.checkbox("我了解並同意以上匿名聲明")

    COOLDOWN = 60
    can_submit = (time.time() - st.session_state.fb_last_ts) > COOLDOWN
    if st.button("送出回饋", type="primary", disabled=not can_submit):
        if not content.strip():
            st.error("請先填寫回饋內容。")
        elif int(ans) != (a+b):
            st.error("驗證題錯誤。")
        elif not agree:
            st.error("請先勾選同意匿名聲明。")
        else:
            ua = st.session_state.get("user_agent", "unknown")
            insert_feedback(content.strip(), (contact.strip() or None), str(ua)[:200], st.session_state.fb_session_hash)
            st.session_state.fb_last_ts = time.time()
            st.success("已收到，謝謝你的回饋！🧡")
            st.toast("感謝你的回饋！", icon="😺")
            st.experimental_rerun()

    st.caption(f"防洗版：每 {COOLDOWN} 秒可提交一次。請勿張貼個資或廣告。")

# 側邊選單（同一連結進入）
page = st.sidebar.radio("功能選單", ["🔎 訂單查詢", "📮 匿名回饋"], index=0)
page_orders() if page == "🔎 訂單查詢" else page_feedback()

#

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
name = st.text_input("請輸入登記包裹用名稱(默認LINE名稱)")
# ✅ 單一濾器：只看未完成（＝未運回）
only_incomplete = st.checkbox("只看未完成訂單（未運回）", value=False)

if st.button("🔎 查詢"):
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



