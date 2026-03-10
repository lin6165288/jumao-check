import streamlit as st
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
# 假資料（之後可改成資料庫讀取）
# =============================
CURRENT_EXCHANGE_RATE = "4.78"
RECENT_SHIPMENTS = [
    "3/12 海快船班｜預計 3/15-3/16 到台",
    "3/15 空運船班｜預計 3/17-3/18 到台",
    "3/18 海快船班｜預計 3/21-3/22 到台",
]

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
            padding-top: 2rem;
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
    st.markdown('<div class="section-title">📢 最新公告</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"""
            <div class="announce-card">
                <div class="card-title">💱 當前匯率</div>
                <div style="font-size: 2rem; font-weight: 800; color:#d2691e; margin: 10px 0;">
                    {CURRENT_EXCHANGE_RATE}
                </div>
                <div class="small-note">※ 此處先為展示用，之後可改成由後台維護或從資料庫自動讀取。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        shipment_html = "".join([f"<li style='margin-bottom:8px;'>{item}</li>" for item in RECENT_SHIPMENTS])
        st.markdown(
            f"""
            <div class="announce-card">
                <div class="card-title">🚢 近期運回船班</div>
                <ul style="padding-left: 20px; margin-top: 14px; color:#5f5f5f; line-height: 1.8;">
                    {shipment_html}
                </ul>
                <div class="small-note">※ 之後可改成由後台直接新增／修改船班資訊。</div>
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
    st.title("📦 查詢訂單")
    st.info("這裡之後可放：訂單查詢表單、查詢結果、訂單進度、物流狀態。")
    st.text_input("訂單編號 / 客戶姓名 / 手機末三碼（示意）")
    st.button("查詢")


def page_faq():
    st.title("❓ 常見 QA")
    st.info("這裡之後可放 FAQ 分類，例如：下單流程、付款、出貨、運費、售後。")

    with st.expander("示意問題 1：代購流程怎麼進行？"):
        st.write("這裡先放示意內容，之後你給我細節我再幫你整理成正式版本。")

    with st.expander("示意問題 2：多久會到貨？"):
        st.write("這裡先放示意內容。")


def page_quote():
    st.title("🧮 自動報價")
    st.info("這裡之後可放：商品金額輸入、手續費規則、匯率換算、自動計算結果。")

    amount = st.number_input("商品金額（人民幣）", min_value=0.0, step=1.0)
    rate = st.number_input("匯率（示意）", min_value=0.0, value=4.78, step=0.01)

    if st.button("試算"):
        estimate = amount * rate
        st.success(f"示意報價：NT$ {estimate:,.0f}")


def page_forwarding_register():
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
