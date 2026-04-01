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
            "1. 查詢訂單、提前運回",
            "輸入姓名查詢訂單狀態，申請提前運回部分包裹。",
            "進入查詢訂單",
            "go_order_query",
            "order_query",
        )

    with row1_col2:
        feature_card(
            "2. 常見 QA、交易須知",
            "整理常見問題，例如付款方式、下單流程、運費規則、到貨時間與售後說明。",
            "查看常見 QA",
            "go_faq",
            "faq",
        )

    with row1_col3:
        feature_card(
            "3. 費用試算",
            "可自行輸入商品金額，快速估算代購價格。",
            "使用費用試算",
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

        # =============================
    # 區塊 1：訂單列表
    # =============================
    with st.container(border=True):
        st.markdown("### 📋 訂單列表")
        st.dataframe(df_table, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()
    st.markdown("<br>", unsafe_allow_html=True)

    # =============================
    # 區塊 2：欲提前運回訂單申請
    # =============================
    selectable_df = df[(df["is_arrived"] == 1) & (df["is_returned"] == 0)].copy()

    with st.container(border=True):
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
            st.caption("尚未選取欲提前運回訂單。")

def page_faq():
    back_to_home_button()

    st.title("❓ 常見 QA / 交易須知")
    st.caption("下單前請先閱讀常見問題與交易規則，如有不清楚的地方請先詢問。")

    keyword = st.text_input("🔍 搜尋關鍵字", placeholder="例如：付款、提確、取消、售後、物流")

    faq_data = {
        "💰 付款相關": [
            {
                "q": "有什麼付款方式？",
                "a": """1. 轉帳付款（目前只提供 LINE Bank）
2. 貨到付款 +30（限商品金額 500 台幣內）
3. 儲值餘額（一次轉帳，購買商品費用從餘額扣除，可省轉帳手續費）

🚫 嚴禁第三方代匯，發現會直接取消交易，嚴重者將報警。"""
            },
            {
                "q": "貨到付款有什麼限制？",
                "a": """貨到付款限商品金額 500 台幣內，並需額外 +30 台幣。

若商品為訂製、預售、需提前確認收貨（tq、提確）等非現貨商品，皆無法使用貨到付款。"""
            },
        ],
        "⚠️ 提確 / 補郵相關": [
            {
                "q": "提確商品是什麼？有風險嗎？",
                "a": """若為需要提前確認收貨（tq、提確）的商品，請先自行確認賣家是否為誠信賣家。

提確後，商品款項會全額進到賣家帳戶。
若事後賣家失聯、帳號消失、惡意不出貨等，無論是哪個平台，款項皆可能無法追回。

❣️ 提確有風險，下單提確商品即視為同意自行承擔風險。"""
            },
            {
                "q": "提確、需補郵的商品需要自己追蹤進度嗎？",
                "a": """需要。

若為提確、需補郵的商品，麻煩自行追蹤商品後續進度（補郵時間、物流寄出單號）。
除非賣家主動提供資訊，否則這邊無法主動幫忙跟進。

💡 後續需補郵的商品，請主動傳補郵連結至聊天室，否則若錯過補郵期間，損失需自行承擔。
💡 若賣家寄出後快遞單號是發在群組內，也請主動傳快遞單號至聊天室。

若未主動追蹤進度導致後續問題，這邊概不負責。"""
            },
        ],
        "🛍 下單 / 訂單相關": [
            {
                "q": "可以幫忙跟賣家溝通嗎？",
                "a": """代購的話，都可以免費幫忙詢問賣家商品問題、溝通訂製商品細節…等等。
                
代付的話，不提供代問，請自行與賣家溝通。

💡不問商品頁面已標出的內容"""
            },
            {
                "q": "可以幫忙議價／小刀嗎？",
                "a": """可以！
若商品頁面設置可以刀 會主動幫忙小刀。也可以自行跟賣家刀完再來請橘貓代購～

請橘貓幫忙議價後，若賣家同意了就一定得購買！

不接受刀完的價又說不要了！（會列入黑名單）

請不要耍賣家 謝謝～"""
            },
            {
                "q": "要如何知道商品進度呢？",
                "a": """商品到齊後，運回台灣前 會通知重量＋運費＋配送方式。
（每週固定運回一批包裹回台）

若太久沒收到通知，歡迎隨時留言詢問！

⏳但請不要隔一天問一次進度～"""
            },
            {
                "q": "下單後可以取消代購商品嗎？",
                "a": """不接受任何下單後因個人因素取消訂單，例如：
未看清商品內文、衝動下單、改變心意等。

若為賣家因素需要取消（如聯絡不上賣家、惡意不發貨等），會協助後續退款，但可能酌收部分手續費。"""
            },
            {
                "q": "購買多件商品會怎麼寄回？",
                "a": """一次代購多件商品時，默認全部包裹都到轉運倉後才會通知運回，這樣通常較省運費。

若有部分商品想先集運回台，請主動告知。
若其中有部分商品為預購、等待時間較久，橘貓也會主動詢問是否要先寄部分商品回台。"""
            },
        ],
        "🧸 售後相關": [
            {
                "q": "收到貨後商品有問題怎麼辦？",
                "a": """收到貨後若商品有任何問題，請第一時間聯絡橘貓。

橘貓會盡力協助與賣家溝通，但由於是跨國交易，常常在收到貨時訂單已自動完成，
再加上中間經過多次物流轉運，若賣家執意不售後，這邊也無法保證一定能處理成功。

📷 若需要售後，請提供開箱影片至聊天室，大多數賣家皆需開箱影片才能處理。
📦 若賣家同意補寄商品，後續運回台灣產生的運費需自行承擔。"""
            },
            {
                "q": "收到的商品與購買商品不一樣怎麼辦？",
                "a": """有機率會遇到賣家寄錯商品、大陸快遞貼錯單號、假貨等風險。

若遇到問題請盡快聯絡橘貓，並提供開箱影片與商品照片，這邊會盡力協助確認與處理。"""
            },
        ],
        "🚚 寄送 / 物流相關": [
            {
                "q": "有什麼寄送方式？",
                "a": """有什麼寄送方式？
1. 711賣貨便（不保價）
2. 711交貨便（運費依保價金額不同）
3. 宅配（配合新竹物流，需註冊EZ WAY）
❣️運費詳情請看價目表
"""
            },
            {
                "q": "下單後多久會收到？",
                "a": """若是選超商配送，一般下單後約兩週左右會收到貨；
若是選擇宅配運回，一般下單後約一週左右會收到貨。

但依下單時間、賣家出貨速度與物流狀況不同，無法保證實際收貨時效。

若是急需商品，建議下單前先詢問橘貓，會更方便協助抓時間。"""
            },
            {
                "q": "7-11 超商寄送有什麼風險？",
                "a": """橘貓不會擅自拆開客戶包裹，會在賣家原包裝基礎上再套破壞袋寄出。

超商物流本身有遺失、毀損、污染包裹的風險，若因此產生損失需自行承擔，橘貓概不負責。

7-11 賣貨便只會賠償賣場商品定價；
若商品較貴重、需要保價寄出，請於寄出前主動告知，改用 7-11 交貨便保價寄出。"""
            },
            {
                "q": "物流造成商品損壞怎麼辦？",
                "a": """代購商品皆為海外運送回台，會經過多次物流運輸，無法保證包裹狀態完好無損。

若商品因物流過程受損，相關風險需自行承擔。
由於無法明確判定是哪一段物流造成損傷，因此通常也無法向物流方求償。"""
            },
        ],
        "📦 申報 / 禁運相關": [
            {
                "q": "商品內容物申報需要注意什麼？",
                "a": """每件包裹運回台灣都需向海關申報進口。

若沒有如實申報商品內容物，導致額外費用、罰款或其他問題，需自行負責。"""
            },
        ],
    }

    notice_data = [
        "下單前請詳閱商品頁面注意事項，下單即視為同意相關規則。",
        "嚴禁任何第三方代匯，發現會直接取消交易，嚴重者將報警。",
        "提確商品、補郵商品屬高風險類型，請務必自行追蹤進度並確認賣家可信度。",
        "不接受任何因個人因素造成的下單後取消。",
        "如需售後，請務必提供開箱影片。",
        "超商物流存在遺失、毀損、污染等風險，若未特別要求保價寄出，視為已知悉相關風險。",
        "商品進口需如實申報內容物，若因此產生費用或罰則需自行承擔。",
        "若有任何不清楚的地方，請務必於下單前先詢問。",
    ]

    has_result = False

    st.markdown("## 常見 QA")
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

    st.markdown("## 交易須知")
    filtered_notice = []
    for notice in notice_data:
        if not keyword or keyword.strip().lower() in notice.lower():
            filtered_notice.append(notice)

    if filtered_notice:
        has_result = True
        for i, notice in enumerate(filtered_notice, start=1):
            st.markdown(f"{i}. {notice}")

    if keyword and not has_result:
        st.info("目前找不到符合的內容，建議直接私訊橘貓詢問。")


def page_quote():
    back_to_home_button()

    st.title("🧮 費用試算")
    st.caption("可先估算商品費用、國際運費與台灣運費，實際金額仍以橘貓最終通知為準。")

    def round_up_half_kg(weight):
        if weight <= 0:
            return 0.0
        return ((weight * 2 + 0.999999) // 1) / 2

    def calc_service_fee(rmb):
        rmb = float(rmb)

        if rmb <= 499:
            return 30
        elif rmb <= 999:
            return 50
        else:
            extra_blocks = int((rmb - 1000) // 500)
            return 100 + (extra_blocks * 50)

    def apply_vip_discount(service_fee, vip_level):
        discount_map = {
            "一般會員": 1.00,
            "VIP1": 0.90,
            "VIP2": 0.85,
            "VIP3": 0.80,
        }
        discounted_fee = service_fee * discount_map.get(vip_level, 1.00)
        return round(discounted_fee)

    current_rate = get_current_exchange_rate()
    try:
        current_rate = float(current_rate)
    except:
        current_rate = 4.78

    st.markdown("### ① 商品費用")

    col1, col2 = st.columns(2)
    with col1:
        amount_rmb = st.number_input("商品金額（人民幣）", min_value=0.0, step=1.0)
    with col2:
        vip_level = st.selectbox("會員等級", ["一般會員", "VIP1", "VIP2", "VIP3"])

    st.markdown("### ② 國際運費")

    col3, col4 = st.columns(2)
    with col3:
        weight_kg = st.number_input("商品重量（公斤）", min_value=0.0, step=0.1)
    with col4:
        delivery_method = st.selectbox("台灣運送方式", ["宅配", "賣貨便"])

    if st.button("開始試算", use_container_width=True):
        # 商品費用
        base_service_fee = calc_service_fee(amount_rmb)
        service_fee = apply_vip_discount(base_service_fee, vip_level)
        product_fee = round(amount_rmb * current_rate + service_fee)

        # 國際運費
        billable_weight = round_up_half_kg(weight_kg)
        international_fee = round(billable_weight * 70)  # 0.5kg 35元 = 1kg 70元

        # 台灣運費
        taiwan_fee = 100 if delivery_method == "宅配" else 38

        total_fee = product_fee + international_fee + taiwan_fee

        st.markdown("### 📋 試算結果")

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("商品費用", f"NT$ {product_fee:,.0f}")
        r2.metric("國際運費", f"NT$ {international_fee:,.0f}")
        r3.metric("台灣運費", f"NT$ {taiwan_fee:,.0f}")
        r4.metric("預估總費用", f"NT$ {total_fee:,.0f}")

        st.markdown("### 明細說明")
        st.write(f"目前匯率：{current_rate}")
        st.write(f"商品金額：{amount_rmb:.0f} 人民幣")
        st.write(f"原始代購手續費：NT$ {base_service_fee}")
        st.write(f"{vip_level} 折扣後手續費：NT$ {service_fee}")
        st.write(f"商品費用 = {amount_rmb:.0f} × {current_rate} + {service_fee} = NT$ {product_fee:,.0f}")
        st.write(f"國際運費計費重量：{billable_weight:.1f} kg")
        st.write(f"國際運費：NT$ {international_fee:,.0f}")
        st.write(f"台灣運費（{delivery_method}）：NT$ {taiwan_fee:,.0f}")

        st.info("此為試算金額，實際費用仍可能依商品狀況、重量、物流安排而調整。")


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
