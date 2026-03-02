import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error

# =============================
# 基本設定
# =============================
st.set_page_config(page_title="橘貓代購｜客戶系統", page_icon="🧡", layout="centered")

db_cfg = st.secrets["mysql"]

def get_connection():
    return mysql.connector.connect(
        host=db_cfg["host"],
        port=int(db_cfg["port"]),
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["database"],
        charset="utf8mb4",
        connection_timeout=10,
    )

# =============================
# 自動建表（只建立「客戶端會用到但可能不存在的表」）
# 不會動你已有的 orders / failed_orders
# =============================
def ensure_client_tables():
    ddl = [
        # FAQ（後台維護，客戶只讀）
        """
        CREATE TABLE IF NOT EXISTS faq_items (
          id INT AUTO_INCREMENT PRIMARY KEY,
          category VARCHAR(255) NOT NULL DEFAULT '一般',
          question VARCHAR(255) NOT NULL,
          answer TEXT NOT NULL,
          sort_order INT NOT NULL DEFAULT 0,
          is_enabled TINYINT(1) NOT NULL DEFAULT 1,
          created_at DATE NULL,
          updated_at DATE NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """,
        # VIP 帳戶（後台維護，客戶只讀）
        """
        CREATE TABLE IF NOT EXISTS vip_accounts (
          id INT AUTO_INCREMENT PRIMARY KEY,
          customer_name VARCHAR(255) NOT NULL UNIQUE,
          vip_level VARCHAR(20) NOT NULL DEFAULT 'VIP0',
          balance_twd DECIMAL(10,2) NOT NULL DEFAULT 0,
          updated_at DATE NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """,
        # 報價設定（後台維護，客戶只讀）
        """
        CREATE TABLE IF NOT EXISTS pricing_settings (
          id INT PRIMARY KEY,
          sell_rate DECIMAL(10,4) NOT NULL DEFAULT 0,
          vip1_discount DECIMAL(6,4) NOT NULL DEFAULT 0.90,
          vip2_discount DECIMAL(6,4) NOT NULL DEFAULT 0.85,
          vip3_discount DECIMAL(6,4) NOT NULL DEFAULT 0.80,
          updated_at DATE NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """,
        # 匿名回饋（客戶寫入，後台讀取）
        """
        CREATE TABLE IF NOT EXISTS feedbacks (
          id INT AUTO_INCREMENT PRIMARY KEY,
          created_at DATE NULL,
          content TEXT NOT NULL,
          status ENUM('未處理','已讀','已回覆','忽略') DEFAULT '未處理',
          staff_note VARCHAR(255) NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """,
    ]

    try:
        conn = get_connection()
        cur = conn.cursor()
        for q in ddl:
            cur.execute(q)

        # pricing_settings 至少有一筆 id=1（沒有就補）
        cur.execute(
            """
            INSERT INTO pricing_settings (id, sell_rate, vip1_discount, vip2_discount, vip3_discount, updated_at)
            VALUES (1, 4.8, 0.90, 0.85, 0.80, CURDATE())
            ON DUPLICATE KEY UPDATE id=id;
            """
        )

        conn.commit()
        conn.close()
    except Error as e:
        st.error(f"資料庫初始化失敗：{e}")

ensure_client_tables()

# =============================
# 共用：手續費規則 & VIP 折扣
# 你的手續費規則：
# 0~499:30
# 500~999:50
# 1000~1499:100
# 1500~1999:150
# 之後每 +500 => +50
# =============================
def calc_service_fee_twd(amount_rmb: float) -> int:
    r = float(amount_rmb or 0)
    if r <= 0:
        return 0
    if r < 500:
        return 30
    if r < 1000:
        return 50
    extra_tiers = int((r - 1000) // 500)  # 1000~1499 => 0
    return 100 + extra_tiers * 50

def get_pricing_settings():
    conn = get_connection()
    s = pd.read_sql("SELECT * FROM pricing_settings WHERE id=1", conn).iloc[0]
    conn.close()
    return s

def get_vip_level_by_name(name: str):
    conn = get_connection()
    df = pd.read_sql(
        "SELECT vip_level FROM vip_accounts WHERE LOWER(TRIM(customer_name))=LOWER(%s) LIMIT 1",
        conn,
        params=[name.strip()],
    )
    conn.close()
    if df.empty:
        return None
    return df.iloc[0]["vip_level"]

def vip_discount(level: str, s) -> float:
    lv = (level or "").upper()
    if lv == "VIP1":
        return float(s["vip1_discount"])
    if lv == "VIP2":
        return float(s["vip2_discount"])
    if lv == "VIP3":
        return float(s["vip3_discount"])
    return 1.0

# =============================
# 客戶端頁面
# =============================
def page_orders():
    st.title("🧡 橘貓代購｜訂單查詢")

    name = st.text_input("請輸入登記包裹用名稱(默認LINE名稱)", key="q_name")
    only_incomplete = st.checkbox("只看未完成訂單（未運回）", value=False, key="q_only_incomplete")

    if st.button("🔎 查詢", key="q_search_btn"):
        if not name.strip():
            st.warning("請先輸入姓名")
            return

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

def page_faq():
    st.title("📘 常見問題（QA）")

    try:
        conn = get_connection()
        df = pd.read_sql(
            """
            SELECT id, category, question, answer
            FROM faq_items
            WHERE is_enabled=1
            ORDER BY sort_order ASC, id ASC
            """,
            conn,
        )
        conn.close()

        if df.empty:
            st.info("目前尚未上架常見問題。")
            return

        keyword = st.text_input("🔍 搜尋關鍵字（問題/答案/分類）", "").strip().lower()
        if keyword:
            df = df[
                df["category"].fillna("").str.lower().str.contains(keyword)
                | df["question"].fillna("").str.lower().str.contains(keyword)
                | df["answer"].fillna("").str.lower().str.contains(keyword)
            ]

        if df.empty:
            st.info("找不到符合的 QA。")
            return

        for cat, g in df.groupby("category", sort=False):
            with st.expander(f"📂 {cat}", expanded=False):
                for _, row in g.iterrows():
                    st.markdown(f"**Q：{row['question']}**")
                    st.markdown(f"A：{row['answer']}")
                    st.divider()

    except Error as e:
        st.error(f"資料庫錯誤：{e}")

def page_vip():
    st.title("⭐ VIP 會員中心")

    name = st.text_input("請輸入登記名稱（與訂單查詢一致）", key="vip_name")
    if st.button("查詢 VIP 資訊", key="vip_query_btn"):
        if not name.strip():
            st.warning("請先輸入姓名")
            return

        try:
            conn = get_connection()
            df = pd.read_sql(
                """
                SELECT customer_name, vip_level, balance_twd
                FROM vip_accounts
                WHERE LOWER(TRIM(customer_name)) = LOWER(%s)
                LIMIT 1
                """,
                conn,
                params=[name.strip()],
            )
            conn.close()

            if df.empty:
                st.info("查無 VIP 資料（可能尚未建檔）。請私訊橘貓協助加入。")
                return

            row = df.iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("會員", row["customer_name"])
            c2.metric("VIP 等級", row["vip_level"])
            c3.metric("儲值餘額（TWD）", f"{float(row['balance_twd']):,.0f}")

            st.caption("折價券（剩餘張數/到期日）之後要加，我們可以再新增 coupon 表。")

        except Error as e:
            st.error(f"資料庫錯誤：{e}")

def page_quote():
    st.title("🧮 自動報價（試算）")

    name = st.text_input("（可選）輸入姓名以套用 VIP 折扣", key="quote_name")
    rmb = st.number_input("人民幣金額（RMB）", min_value=0.0, value=0.0, step=1.0)

    try:
        s = get_pricing_settings()
        sell_rate = float(s["sell_rate"])

        vip_level = get_vip_level_by_name(name) if name.strip() else None
        disc = vip_discount(vip_level, s)

        fee = calc_service_fee_twd(rmb)
        total = rmb * sell_rate + fee * disc

        st.subheader("📌 試算結果")
        a, b, c = st.columns(3)
        a.metric("收費匯率", f"{sell_rate:.2f}")
        b.metric("手續費（折扣前）", f"{fee:.0f} TWD")
        c.metric("VIP 折扣", f"{disc:.2f}" + (f"（{vip_level}）" if vip_level else ""))

        st.success(f"✅ 參考報價：約 **{total:,.0f} TWD**")
        st.caption("此為試算報價，實際仍以橘貓最終結算明細為準。")

        st.code(
            f"報價試算：RMB {rmb:.0f} × 匯率 {sell_rate:.2f} + 手續費 {fee:.0f} × 折扣 {disc:.2f} ＝ 約 {total:,.0f} TWD",
            language="text",
        )

    except Exception as e:
        st.error(f"讀取設定失敗：{e}")

def page_feedback():
    st.title("📮 匿名回饋")
    st.info("有任何想法、建議，或希望看到的新功能嗎？🧡 請放心留下訊息，我們都會認真參考！", icon="😺")

    flash = st.session_state.pop("fb_flash", None)
    if flash:
        st.success(flash)
    if st.session_state.pop("fb_clear", False):
        st.session_state.pop("fb_content", None)

    content = st.text_area("寫下你想對橘貓說的話（匿名）", height=200, key="fb_content")
    if st.button("送出回饋", type="primary"):
        if not content.strip():
            st.error("請先填寫回饋內容。")
            return
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO feedbacks (created_at, content) VALUES (CURDATE(), %s)",
                (content.strip(),),
            )
            conn.commit()
            conn.close()

            st.session_state["fb_flash"] = "已收到，謝謝你的回饋！🧡"
            st.session_state["fb_clear"] = True
            st.rerun()
        except Error as e:
            st.error(f"寫入失敗：{e}")

# =============================
# =============================
# 首頁大選單導覽（你要的：先選功能才進頁面）
# =============================
if "page" not in st.session_state:
    st.session_state["page"] = "home"

def go(page_name: str):
    st.session_state["page"] = page_name
    st.rerun()

def top_bar():
    # 不是首頁就顯示返回
    if st.session_state["page"] != "home":
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("⬅ 回首頁"):
                go("home")
        with col2:
            st.caption("🧡 橘貓代購｜客戶系統")

# ----- 首頁 -----
if st.session_state["page"] == "home":
    st.title("🧡 橘貓代購｜客戶系統")
    st.caption("請先選擇你要使用的功能")

    st.write("")

    # 兩排大按鈕（你可以調整排版）
    r1 = st.columns(2)
    with r1[0]:
        if st.button("🔎 訂單查詢", use_container_width=True):
            go("orders")
    with r1[1]:
        if st.button("📘 常見問題（QA）", use_container_width=True):
            go("faq")

    r2 = st.columns(2)
    with r2[0]:
        if st.button("⭐ VIP 會員", use_container_width=True):
            go("vip")
    with r2[1]:
        if st.button("🧮 自動報價", use_container_width=True):
            go("quote")

    r3 = st.columns(1)
    with r3[0]:
        if st.button("📮 匿名回饋", use_container_width=True):
            go("feedback")

# ----- 內頁 -----
else:
    top_bar()

    page = st.session_state["page"]
    if page == "orders":
        page_orders()
    elif page == "faq":
        page_faq()
    elif page == "vip":
        page_vip()
    elif page == "quote":
        page_quote()
    elif page == "feedback":
        page_feedback()
    else:
        # fallback
        go("home")
