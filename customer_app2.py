import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime

# =============================
# 基本設定
# =============================
st.set_page_config(
    page_title="橘貓代購｜客戶系統",
    page_icon="🧡",
    layout="wide"
)

# =============================
# 資料庫連線
# =============================
def get_connection():
    conn = mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        port=int(st.secrets["mysql"]["port"]),
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        charset="utf8mb4",
        connection_timeout=10,
    )
    cur = conn.cursor()
    cur.execute("SET time_zone = '+08:00'")
    cur.close()
    return conn

def get_current_exchange_rate():
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT setting_value
            FROM site_settings
            WHERE setting_key = 'current_exchange_rate'
            LIMIT 1
        """, conn)

        if df.empty:
            return "4.78"
        return str(df.iloc[0]["setting_value"])
    except:
        return "4.78"
    finally:
        conn.close()


def get_recent_shipping_batches(delivery_method=None):
    conn = get_connection()
    try:
        sql = """
            SELECT batch_text
            FROM shipping_batches
            WHERE is_active = 1
        """
        params = []

        if delivery_method == "宅配":
            sql += " AND delivery_type = %s"
            params.append("home_delivery")
        elif delivery_method == "賣貨便":
            sql += " AND delivery_type = %s"
            params.append("shop_delivery")

        sql += " ORDER BY sort_order ASC, batch_id DESC"

        df = pd.read_sql(sql, conn, params=params)

        if df.empty:
            return []
        return df["batch_text"].tolist()
    except Exception:
        return []
    finally:
        conn.close()

def ensure_return_request_tables(conn):
    ddl1 = """
    CREATE TABLE IF NOT EXISTS customer_return_requests (
      request_id INT AUTO_INCREMENT PRIMARY KEY,
      customer_name VARCHAR(255) NOT NULL,
      selected_shipping_batch VARCHAR(255) NOT NULL,
      delivery_method VARCHAR(50) NOT NULL DEFAULT '面交/自取',
      total_count INT NOT NULL DEFAULT 0,
      total_weight DECIMAL(10,3) NOT NULL DEFAULT 0,
      estimated_fee DECIMAL(10,2) NOT NULL DEFAULT 0,
      status ENUM('pending','processed','cancelled') NOT NULL DEFAULT 'pending',
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """

    ddl2 = """
    CREATE TABLE IF NOT EXISTS customer_return_request_items (
      id INT AUTO_INCREMENT PRIMARY KEY,
      request_id INT NOT NULL,
      order_id INT NOT NULL,
      tracking_number VARCHAR(255) NULL,
      platform VARCHAR(50) NULL,
      weight_kg DECIMAL(10,3) NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE KEY uk_request_order (request_id, order_id),
      CONSTRAINT fk_return_req_items_request
        FOREIGN KEY (request_id) REFERENCES customer_return_requests(request_id)
        ON DELETE CASCADE
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """

    with conn.cursor() as cur:
        cur.execute(ddl1)
        cur.execute(ddl2)
    conn.commit()


def save_return_request(
    customer_name,
    selected_shipping_batch,
    delivery_method,
    selected_df,
    total_count,
    total_weight,
    estimated_fee
):
    conn = get_connection()
    try:
        ensure_return_request_tables(conn)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO customer_return_requests
                (
                    customer_name,
                    selected_shipping_batch,
                    delivery_method,
                    total_count,
                    total_weight,
                    estimated_fee,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                """,
                (
                    customer_name,
                    selected_shipping_batch,
                    delivery_method,
                    int(total_count),
                    float(total_weight),
                    float(estimated_fee),
                )
            )
            request_id = cur.lastrowid

            item_sql = """
            INSERT INTO customer_return_request_items
            (
                request_id,
                order_id,
                tracking_number,
                platform,
                weight_kg
            )
            VALUES (%s, %s, %s, %s, %s)
            """

            for _, row in selected_df.iterrows():
                cur.execute(
                    item_sql,
                    (
                        int(request_id),
                        int(row["order_id"]),
                        str(row["tracking_number"]) if pd.notna(row["tracking_number"]) else "",
                        str(row["platform"]) if pd.notna(row["platform"]) else "",
                        float(row["weight_kg"]) if pd.notna(row["weight_kg"]) else 0.0,
                    )
                )

        conn.commit()
        return True, request_id, None

    except Exception as e:
        conn.rollback()
        return False, None, str(e)

    finally:
        conn.close()
        

# =============================
# 假資料（之後可改成資料庫讀取）
# =============================

# =============================
# 共用樣式
# =============================
def inject_custom_css():
    st.markdown(
        """
        <style>
        .main {
            background-color: #fffaf5;
        }

        .block-container {
            padding-top: 4.5rem;
            padding-bottom: 3rem;
            max-width: 1200px;
        }

        .hero-box {
            background: linear-gradient(135deg, #fff3e8 0%, #ffe8d6 100%);
            border: 1px solid #f4c9a8;
            border-radius: 20px;
            padding: 24px;
            margin-bottom: 24px;
        }

        .announce-card {
            background: white;
            border-radius: 18px;
            padding: 20px;
            border: 1px solid #f2d4bf;
            box-shadow: 0 4px 12px rgba(0,0,0,0.04);
            min-height: 180px;
        }

        .section-title {
            font-size: 1.6rem;
            font-weight: 700;
            color: #8b4513;
            margin-top: 8px;
            margin-bottom: 12px;
        }

        .card-title {
            font-size: 1.2rem;
            font-weight: 700;
            color: #7a3d17;
            margin-bottom: 10px;
        }

        .card-desc {
            color: #5f5f5f;
            font-size: 0.96rem;
            line-height: 1.7;
            min-height: 72px;
        }

        .feature-card {
            background: white;
            border-radius: 18px;
            padding: 20px;
            border: 1px solid #f2d4bf;
            box-shadow: 0 4px 12px rgba(0,0,0,0.04);
            margin-bottom: 14px;
        }

        .small-note {
            color: #777;
            font-size: 0.88rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =============================
# 共用元件
# =============================
def show_header():
    st.markdown(
        f"""
        <div class="hero-box">
            <h1 style="margin-bottom: 8px; color:#8b4513;">🧡 橘貓代購｜客戶系統</h1>
            <div style="font-size: 1rem; color:#6b4b3e;">
                歡迎來到橘貓代購客戶平台，可以在這裡查詢訂單、查看公告、使用自助功能。
            </div>
            <div style="margin-top:10px; color:#8a6a57; font-size:0.9rem;">
                最後更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def announcement_section():
    current_exchange_rate = get_current_exchange_rate()
    recent_shipments = get_recent_shipping_batches()

    st.markdown('<div class="section-title">📢 最新公告</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"""
            <div class="announce-card">
                <div class="card-title">💱 當前匯率</div>
                <div style="font-size: 2rem; font-weight: 800; color:#d2691e; margin: 10px 0;">
                    {current_exchange_rate}
                </div>
                <div class="small-note">※ 此匯率由後台更新。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        if recent_shipments:
            shipment_html = "".join([f"<li style='margin-bottom:8px;'>{item}</li>" for item in recent_shipments])
        else:
            shipment_html = "<li>目前尚無船班公告</li>"

        st.markdown(
            f"""
            <div class="announce-card">
                <div class="card-title">🚢 近期運回船班</div>
                <ul style="padding-left: 20px; margin-top: 14px; color:#5f5f5f; line-height: 1.8;">
                    {shipment_html}
                </ul>
                <div class="small-note">※ 此資訊由後台更新。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def feature_card(title, desc, button_text, key, target_page):
    st.markdown(
        f"""
        <div class="feature-card">
            <div class="card-title">{title}</div>
            <div class="card-desc">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(button_text, key=key, use_container_width=True):
        st.session_state["page"] = target_page
        st.rerun()

def back_to_home_button():
    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("← 返回首頁", use_container_width=True):
            st.session_state["page"] = "home"
            st.rerun()


# =============================
# 各功能頁面（先放大架構）
# =============================
def page_home():
    show_header()
    announcement_section()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">🛠 功能選單</div>', unsafe_allow_html=True)

    row1_col1, row1_col2, row1_col3 = st.columns(3)
    row2_col1, row2_col2, row2_col3 = st.columns(3)

    with row1_col1:
        feature_card(
            "1. 查詢訂單",
            "讓客戶輸入姓名、電話、訂單編號或其他識別資訊，查詢自己的訂單狀態。",
            "進入查詢訂單",
            "go_order_query",
            "order_query",
        )

    with row1_col2:
        feature_card(
            "2. 常見 QA",
            "整理常見問題，例如付款方式、下單流程、運費規則、到貨時間與售後說明。",
            "查看常見 QA",
            "go_faq",
            "faq",
        )

    with row1_col3:
        feature_card(
            "3. 自動報價",
            "客戶可自行輸入商品金額、匯率或其他條件，快速估算代購價格。",
            "使用自動報價",
            "go_quote",
            "quote",
        )

    with row2_col1:
        feature_card(
            "4. 集運客戶登記集運包裹",
            "提供集運客戶自行填寫快遞單號、品項與備註，方便後台核對與入庫。",
            "登記集運包裹",
            "go_forwarding",
            "forwarding_register",
        )

    with row2_col2:
        feature_card(
            "5. 會員專區",
            "未來可放會員登入、優惠券、會員等級、歷史訂單、通知紀錄等功能。",
            "進入會員專區",
            "go_member",
            "member_center",
        )

    with row2_col3:
        feature_card(
            "6. 匿名回饋",
            "提供客戶匿名填寫意見、建議或使用心得，讓你能收集真實回饋。",
            "填寫匿名回饋",
            "go_feedback",
            "anonymous_feedback",
        )


def page_order_query():
    back_to_home_button()
    # ===== session state 初始化（一定要放最前面）=====
    st.session_state.setdefault("client_query_name", "")
    st.session_state.setdefault("client_query_show_all", False)
    st.session_state.setdefault("client_query_submitted", False)
    st.session_state.setdefault("client_query_df", None)
    st.session_state.setdefault("return_selector_reset_counter", 0)
    st.session_state.setdefault("return_request_sent", False)
    st.session_state.setdefault("show_success_box", False)
    st.session_state.setdefault("success_box_message", "")

    st.title("📦 查詢訂單")
    st.caption("輸入名稱後查詢訂單，並可選取欲提前運回的訂單與船班。")

    def round_up_half_kg(weight):
        if weight <= 0:
            return 0.0
        return ((weight * 2 + 0.999999) // 1) / 2

    def calc_estimated_shipping_fee(selected_df, delivery_method):
        if selected_df.empty:
            return 0, 0.0, 0.0, 0.0

        df_calc = selected_df.copy()
        df_calc["platform"] = df_calc["platform"].astype(str).str.strip()
        df_calc["weight_kg"] = pd.to_numeric(df_calc["weight_kg"], errors="coerce").fillna(0.0)

        forwarding_weight = float(df_calc[df_calc["platform"] == "集運"]["weight_kg"].sum())
        other_weight = float(df_calc[df_calc["platform"] != "集運"]["weight_kg"].sum())

        forwarding_billable = 0.0
        other_billable = 0.0
        shipping_fee = 0.0

        if forwarding_weight > 0:
            forwarding_billable = max(1.0, round_up_half_kg(forwarding_weight))
            shipping_fee += forwarding_billable * 90

        if other_weight > 0:
            other_billable = round_up_half_kg(other_weight)
            shipping_fee += other_billable * 70

        if delivery_method == "宅配":
            shipping_fee += 100
        elif delivery_method == "賣貨便":
            shipping_fee += 38

        total_billable = forwarding_billable + other_billable
        return round(shipping_fee), total_billable, forwarding_billable, other_billable

    st.markdown("### 🔍 查詢條件")
    with st.form("order_query_form"):
        customer_name_input = st.text_input(
            "登記包裹用名稱（默認 LINE 名稱）",
            value=st.session_state.get("client_query_name", ""),
            placeholder="請輸入名稱"
        )
        show_all_history = st.checkbox(
            "查看過去所有訂單",
            value=st.session_state.get("client_query_show_all", False)
        )
        submitted = st.form_submit_button("查詢訂單")

    if submitted:
        customer_name_input = customer_name_input.strip()
        st.session_state["client_query_name"] = customer_name_input
        st.session_state["client_query_show_all"] = show_all_history
        st.session_state["client_query_submitted"] = True

        if not customer_name_input:
            st.session_state["client_query_df"] = None
            st.warning("請先輸入登記包裹用名稱。")
            return

        try:
            conn = get_connection()

            if show_all_history:
                sql = """
                SELECT
                    order_id,
                    order_time,
                    customer_name,
                    platform,
                    tracking_number,
                    amount_rmb,
                    weight_kg,
                    is_arrived,
                    is_returned,
                    remarks,
                    service_fee,
                    early_return,
                    is_early_returned
                FROM orders
                WHERE customer_name = %s
                ORDER BY order_time DESC, order_id DESC
                """
                df = pd.read_sql(sql, conn, params=[customer_name_input])
            else:
                sql = """
                SELECT
                    order_id,
                    order_time,
                    customer_name,
                    platform,
                    tracking_number,
                    amount_rmb,
                    weight_kg,
                    is_arrived,
                    is_returned,
                    remarks,
                    service_fee,
                    early_return,
                    is_early_returned
                FROM orders
                WHERE customer_name = %s
                  AND is_returned = 0
                ORDER BY order_time DESC, order_id DESC
                """
                df = pd.read_sql(sql, conn, params=[customer_name_input])

            for col in ["is_arrived", "is_returned", "is_early_returned", "early_return"]:
                if col in df.columns:
                    df[col] = df[col].fillna(0).astype(int)

            if "weight_kg" in df.columns:
                df["weight_kg"] = pd.to_numeric(df["weight_kg"], errors="coerce").fillna(0.0)

            if "amount_rmb" in df.columns:
                df["amount_rmb"] = pd.to_numeric(df["amount_rmb"], errors="coerce").fillna(0.0)

            st.session_state["client_query_df"] = df
            st.session_state["return_request_sent"] = False

        except Exception as e:
            st.session_state["client_query_df"] = None
            st.error(f"查詢訂單失敗：{e}")
            return
        finally:
            try:
                conn.close()
            except:
                pass

    if not st.session_state["client_query_submitted"]:
        st.info("請先輸入登記包裹用名稱，再按下「查詢訂單」。")
        return

    df = st.session_state["client_query_df"]

    if df is None or df.empty:
        st.warning("查無符合的訂單資料。")
        return
        
    st.success(f"查詢成功，共找到 {len(df)} 筆訂單。")

    def get_arrived_status(row):
        tracking = "" if pd.isna(row["tracking_number"]) else str(row["tracking_number"]).strip()
        if int(row["is_arrived"]) == 1:
            return "已到倉"
        return "運送中" if tracking else "賣家尚未寄出"

    df_display = df.copy()
    df_display["到倉狀態"] = df_display.apply(get_arrived_status, axis=1)
    df_display["運回狀態"] = df_display["is_returned"].apply(lambda x: "已運回" if int(x) == 1 else "未運回")

    if "order_time" in df_display.columns:
        df_display["order_time"] = df_display["order_time"].astype(str)

    if "tracking_number" in df_display.columns:
        df_display["tracking_number"] = df_display["tracking_number"].fillna("")

    df_table = df_display[[
        "order_id",
        "order_time",
        "platform",
        "tracking_number",
        "amount_rmb",
        "weight_kg",
        "到倉狀態",
        "運回狀態",
    ]].rename(columns={
        "order_id": "訂單編號",
        "order_time": "下單日期",
        "platform": "平台",
        "tracking_number": "快遞單號",
        "amount_rmb": "金額",
        "weight_kg": "商品重量(kg)",
    })

    st.markdown("### 📋 訂單列表")
    st.dataframe(df_table, use_container_width=True, hide_index=True)

    selectable_df = df[(df["is_arrived"] == 1) & (df["is_returned"] == 0)].copy()

    st.markdown("### 🚢 欲提前運回訂單申請")

    if selectable_df.empty:
        st.info("目前沒有可選取運回的訂單。")
        return

    st.write("只有【已到倉】的包裹可以選取。")
    st.markdown("#### 請選取欲提前運回的訂單")

    selectable_df["selected"] = False

    editable_df = selectable_df[[
        "selected",
        "order_id",
        "order_time",
        "platform",
        "tracking_number",
        "amount_rmb",
        "weight_kg",
    ]].rename(columns={
        "selected": "選取",
        "order_id": "訂單編號",
        "order_time": "下單日期",
        "platform": "平台",
        "tracking_number": "快遞單號",
        "amount_rmb": "金額",
        "weight_kg": "商品重量(kg)",
    })

    editor_key = f"return_order_selector_table_{st.session_state['return_selector_reset_counter']}"

    edited_df = st.data_editor(
        editable_df,
        use_container_width=True,
        hide_index=True,
        disabled=["訂單編號", "下單日期", "平台", "快遞單號", "金額", "商品重量(kg)"],
        column_config={
            "選取": st.column_config.CheckboxColumn(
                "選取",
                help="勾選要運回的訂單",
                default=False,
            )
        },
        key=editor_key
    )

    selected_df = edited_df[edited_df["選取"] == True].copy()

    if not selected_df.empty:
        selected_df = selected_df.rename(columns={
            "訂單編號": "order_id",
            "下單日期": "order_time",
            "平台": "platform",
            "快遞單號": "tracking_number",
            "金額": "amount_rmb",
            "商品重量(kg)": "weight_kg",
        })

        total_count = len(selected_df)
        total_weight = float(selected_df["weight_kg"].sum())

        delivery_method = st.radio(
            "請選擇台灣端寄送方式",
            options=["面交/自取", "宅配", "賣貨便"],
            horizontal=True,
            key="client_delivery_method"
        )

        estimated_fee, billable_weight, forwarding_billable, other_billable = calc_estimated_shipping_fee(
            selected_df,
            delivery_method
        )

        st.markdown("#### 📦 欲運回資訊")
        info1, info2, info3 = st.columns(3)
        info1.metric("總包裹件數", f"{total_count} 件")
        info2.metric("總重量", f"{total_weight:.2f} kg")
        info3.metric("預估運費", f"NT$ {estimated_fee:,.0f}")

        detail_parts = []
        if forwarding_billable > 0:
            detail_parts.append(f"純集運計費重量 {forwarding_billable:.2f} kg × 90")
        if other_billable > 0:
            detail_parts.append(f"代購商品計費重量 {other_billable:.2f} kg × 70")
        if delivery_method == "宅配":
            detail_parts.append("宅配 +100")
        elif delivery_method == "賣貨便":
            detail_parts.append("賣貨便 +38")

        if detail_parts:
            st.caption("＋".join(detail_parts))

        st.caption("純集運：每公斤 90 元，最低 1 公斤起算，並以 0.5 公斤為單位計費；代購商品：每公斤 70 元，以 0.5 公斤為單位計費；宅配加 100 元，賣貨便加 38 元。")

        selected_table = selected_df[["order_id", "order_time", "platform", "tracking_number", "weight_kg"]].copy()
        selected_table = selected_table.rename(columns={
            "order_id": "訂單編號",
            "order_time": "下單日期",
            "platform": "平台",
            "tracking_number": "快遞單號",
            "weight_kg": "重量(kg)",
        })
        st.dataframe(selected_table, use_container_width=True, hide_index=True)

        available_shipping_batches = get_recent_shipping_batches(delivery_method)

        if delivery_method == "面交/自取":
            st.info("面交/自取不需選擇船班。")
            selected_batch = "面交/自取"
        elif not available_shipping_batches:
            st.warning(f"目前沒有可選擇的{delivery_method}船班。")
            selected_batch = None
        else:
            selected_batch = st.selectbox(
                "請選擇欲運回的船班",
                options=available_shipping_batches,
                index=None,
                placeholder="請選擇船班",
                key="client_selected_shipping_batch"
            )

        success_box_placeholder = st.empty()

        if st.button(
            "✅ 確認這批欲運回訂單",
            use_container_width=True,
            disabled=st.session_state.get("return_request_sent", False)
        ):
            if not selected_batch:
                st.warning("請先選擇欲運回的船班。")
            else:
                ok, request_id, err = save_return_request(
                    customer_name=st.session_state["client_query_name"],
                    selected_shipping_batch=selected_batch,
                    delivery_method=delivery_method,
                    selected_df=selected_df,
                    total_count=total_count,
                    total_weight=total_weight,
                    estimated_fee=estimated_fee
                )

                if ok:
                    st.session_state["success_box_message"] = f"已送出運回申請！申請編號：#{request_id}"
                    st.session_state["show_success_box"] = True
                    st.session_state["return_request_sent"] = True
                else:
                    st.error(f"送出失敗：{err}")

        if st.session_state.get("show_success_box", False):
            with success_box_placeholder.container():
                st.success(st.session_state.get("success_box_message", "已送出申請！"))
                st.info("若要取消運回，請直接私訊橘貓協助處理。")
        else:
                st.caption("尚未選取欲運回訂單。")

def page_faq():
    back_to_home_button()

    st.title("❓ 常見 QA")
    st.caption("整理常見問題，方便快速查找。")

    keyword = st.text_input("🔍 搜尋問題關鍵字", placeholder="例如：付款、運費、到貨、集運、課稅")

    faq_data = {
        "💰 付款相關": [
            {
                "q": "有什麼付款方式？",
                "a": """1. 轉帳付款（目前只提供 LINE Bank）
2. 貨到付款 +30（限商品金額 500 台幣內）
3. 儲值餘額（一次轉帳，購買商品費用從餘額扣除，可省轉帳手續費）

🚫 嚴禁第三方代匯，發現會直接取消交易並拉黑，嚴重者將報警。"""
            },
            {
                "q": "餘額可以提領嗎？",
                "a": """可以。

若暫時沒有想要代購的商品，可以提供銀行帳戶至聊天室，會全額退款。

💡 退回帳戶需與轉帳帳戶相同
🚫 反覆轉進轉出者，將直接列入黑名單，嚴重者將報警。"""
            },
        ],
        "📦 寄送 / 運送相關": [
            {
                "q": "有什麼寄送方式？",
                "a": """1. 7-11 賣貨便（不保價）
2. 7-11 交貨便（運費依保價金額不同）
3. 宅配（配合新竹物流，需註冊 EZ WAY）

❣️ 運費詳情請看價目表。"""
            },
            {
                "q": "要如何知道商品進度呢？",
                "a": """商品到齊後、運回台灣前，會通知重量＋運費＋配送方式。
目前為每週固定運回一批包裹回台。

若太久沒收到通知，歡迎隨時留言詢問。
⏳ 但請不要隔一天問一次進度。"""
            },
            {
                "q": "回覆訊息時間？",
                "a": """由於橘貓為單人作業，沒有固定回覆時間，有看到訊息就會盡快回覆。

回覆訊息、下單、登記包裹、理貨、出貨等流程都較繁瑣且耗時，麻煩請耐心等候。"""
            },
            {
                "q": "是否會被課稅？",
                "a": """基本上不太會。

國際運費的價格皆為「包頻繁稅」的價格，但少部分客人仍可能產生額外稅金或棧板費（包裹超過十才）。
若有額外費用，會在運回台灣前先說明，收費透明，可以放心。"""
            },
        ],
        "🛍 代購服務相關": [
            {
                "q": "可以幫忙跟賣家溝通嗎？",
                "a": """可以。

代購的話，都可以免費幫忙詢問賣家商品問題、溝通訂製商品細節等。
代付的話，不提供代問，請自行與賣家溝通。

💡 商品頁面已經清楚標示的內容，不另外代問。"""
            },
            {
                "q": "可以幫忙議價／小刀嗎？",
                "a": """可以。

若商品頁面有設置可刀，會主動幫忙小刀；也可以自行先跟賣家議價完成後，再請橘貓代購。

⚠️ 請注意：
若請橘貓幫忙議價，賣家同意後就一定要購買。
不接受刀完價格後又說不要，這會列入黑名單。
請不要耍賣家，謝謝配合。"""
            },
            {
                "q": "可以幫忙搶限量商品嗎？",
                "a": """可以，但會視情況加收手續費。

最晚請提前一日告知搶購日期、時間與商品連結。
若確認有搶到再收費，不需提前付款。"""
            },
            {
                "q": "閒魚可以幫忙競標商品嗎？",
                "a": "不行。由於競標商品有時間性以及保證金問題，因此競標商品不代購。"
            },
        ],
        "🧸 商品 / 售後相關": [
            {
                "q": "收到的商品與購買商品不一樣怎麼辦？",
                "a": """請第一時間聯絡橘貓告知情況。

會先協助確認是大陸物流貼錯單號，還是哪個環節出了問題。
若為賣家問題，需提供開箱影片，以便協助售後處理。

💡 再次提醒：收到貨務必拍攝開箱影片，以保障自身權益。"""
            },
            {
                "q": "小卡類商品是否可以先看對光再決定要不要購買？",
                "a": """若賣家商品頁面有清楚標明可先私訊看對光，可以協助先詢問對光，確認沒問題後再購買。

若商品頁面沒有特別寫明，則一律為下單付款後再跟賣家索取對光確認狀態。
若對光後發現有瑕疵、傷痕等問題，仍可再協助退款，不會強買強賣。"""
            },
        ],
        "🚫 集運 / 禁運相關": [
            {
                "q": "禁運商品有哪些？",
                "a": """若不確定商品是否可以進口，請先傳商品連結給橘貓確認。

由於集運為海快，任何食品、植物、肉類皆無法進口。
集運規定較繁瑣，先傳連結詢問會是最安全的做法。"""
            },
        ],
    }

    has_result = False

    for category, items in faq_data.items():
        filtered_items = []
        for item in items:
            text = f"{item['q']} {item['a']}"
            if not keyword or keyword.strip().lower() in text.lower():
                filtered_items.append(item)

        if filtered_items:
            has_result = True
            st.markdown(f"### {category}")
            for item in filtered_items:
                with st.expander(item["q"]):
                    st.write(item["a"])

    if keyword and not has_result:
        st.info("目前找不到符合的 QA，建議直接私訊橘貓詢問。")


def page_quote():
    back_to_home_button()

    st.title("🧮 自動報價")
    st.info("這裡之後可放：商品金額輸入、手續費規則、匯率換算、自動計算結果。")

    amount = st.number_input("商品金額（人民幣）", min_value=0.0, step=1.0)
    rate = st.number_input("匯率（示意）", min_value=0.0, value=4.78, step=0.01)

    if st.button("試算"):
        estimate = amount * rate
        st.success(f"示意報價：NT$ {estimate:,.0f}")


def page_forwarding_register():
    back_to_home_button()

    st.title("📮 集運客戶登記集運包裹")
    st.info("這裡之後可放：客戶填寫單號、貨品名稱、備註、圖片上傳、送出登記。")

    with st.form("forwarding_form"):
        st.text_input("客戶姓名")
        st.text_input("快遞單號")
        st.text_input("貨品名稱")
        st.text_area("備註")
        submitted = st.form_submit_button("送出登記")
        if submitted:
            st.success("已送出（目前為示意頁面，尚未寫入資料庫）。")


def page_member_center():
    back_to_home_button()

    st.title("👤 會員專區")
    st.info("這裡之後可放：登入、會員資料、優惠券、訂單紀錄、專屬通知。")

    tab1, tab2 = st.tabs(["登入 / 註冊", "會員功能預覽"])

    with tab1:
        st.text_input("帳號")
        st.text_input("密碼", type="password")
        st.button("登入")

    with tab2:
        st.write("- 我的優惠券")
        st.write("- 我的訂單")
        st.write("- 通知中心")
        st.write("- 會員等級")


def page_anonymous_feedback():
    back_to_home_button()

    st.title("📝 匿名回饋")
    st.info("這裡之後可放：匿名意見表單、分類、評分、送出後寫入 feedback 資料表。")

    with st.form("anonymous_feedback_form"):
        st.selectbox("回饋類型", ["建議", "問題回報", "服務體驗", "其他"])
        st.text_area("想說的內容")
        submitted = st.form_submit_button("送出回饋")
        if submitted:
            st.success("感謝你的回饋！（目前為示意頁面）")


# =============================
# 側邊欄導覽
# =============================
def sidebar_navigation():
    st.sidebar.title("🧡 橘貓代購")
    st.sidebar.caption("客戶端功能選單")

    nav_map = {
        "🏠 首頁": "home",
        "📦 查詢訂單": "order_query",
        "❓ 常見 QA": "faq",
        "🧮 自動報價": "quote",
        "📮 集運包裹登記": "forwarding_register",
        "👤 會員專區": "member_center",
        "📝 匿名回饋": "anonymous_feedback",
    }

    for label, page_key in nav_map.items():
        if st.sidebar.button(label, use_container_width=True):
            st.session_state["page"] = page_key
            st.rerun()


# =============================
# 主程式
# =============================
def main():
    inject_custom_css()
    sidebar_navigation()

    if "page" not in st.session_state:
        st.session_state["page"] = "home"

    page = st.session_state["page"]

    if page == "home":
        page_home()
    elif page == "order_query":
        page_order_query()
    elif page == "faq":
        page_faq()
    elif page == "quote":
        page_quote()
    elif page == "forwarding_register":
        page_forwarding_register()
    elif page == "member_center":
        page_member_center()
    elif page == "anonymous_feedback":
        page_anonymous_feedback()
    else:
        page_home()

    st.markdown("---")
    st.caption("橘貓代購 © 2026｜此版本為客戶端網站功能骨架")


if __name__ == "__main__":
    main()
