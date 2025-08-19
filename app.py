import streamlit as st
import mysql.connector
import pandas as pd
import time
from datetime import datetime
import io
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

# ===== 表格格式化工具：欄位改中文＋布林值轉 ✔ / ✘ =====
def format_order_df(df):
    column_mapping = {
        "order_id": "訂單編號",
        "order_time": "下單日期",
        "customer_name": "客戶姓名",
        "platform": "平台",
        "tracking_number": "包裹單號",
        "amount_rmb": "金額（人民幣）",
        "weight_kg": "公斤數",
        "is_arrived": "是否到貨",
        "is_returned": "是否已運回",
        "is_early_returned": "提前運回",
        "service_fee": "代購手續費",
        "remarks": "備註",
        "匯率價差利潤": "匯率價差利潤",
        "代購手續費收入": "代購手續費收入",
        "總利潤": "總利潤"
    }
    df = df.rename(columns=column_mapping)
    if "是否到貨" in df.columns:
        df["是否到貨"] = df["是否到貨"].apply(lambda x: "✔" if x else "✘")
    if "是否已運回" in df.columns:
        df["是否已運回"] = df["是否已運回"].apply(lambda x: "✔" if x else "✘")
    if "提前運回" in df.columns:
        df["提前運回"] = df["提前運回"].apply(lambda x: "✔" if x else "✘")
    return df

# ===== 資料庫連線 =====

conn = mysql.connector.connect(
    host     = st.secrets["mysql"]["host"],
    user     = st.secrets["mysql"]["user"],
    password = st.secrets["mysql"]["password"],
    database = st.secrets["mysql"]["database"],
)


cursor = conn.cursor(dictionary=True)

st.set_page_config(page_title="橘貓代購系統", layout="wide")
st.title("🐾 橘貓代購｜訂單管理系統")

# ===== 側邊功能選單 =====
menu = st.sidebar.selectbox("功能選單", [
    "📋 訂單總表", "🧾 新增訂單", "✏️ 編輯訂單",
    "🔍 搜尋訂單", "📦 可出貨名單", "🚚 批次出貨", "💰 利潤報表/匯出"
])

# ===== 功能實作 =====

# 1. 訂單總表
if menu == "📋 訂單總表":
    st.subheader("📋 訂單總表")
    df = pd.read_sql("SELECT * FROM orders", conn)
    col1, col2, col3 = st.columns(3)
    with col1:
        arrived_filter = st.selectbox("是否到貨", ["全部", "是", "否"])
    with col2:
        returned_filter = st.selectbox("是否已運回", ["全部", "是", "否"])
    with col3:
        platform_filter = st.selectbox("平台", ["全部", "集運", "拼多多", "淘寶", "閒魚", "1688", "微店", "小紅書"])
    if arrived_filter != "全部":
        df = df[df["is_arrived"] == (arrived_filter == "是")]
    if returned_filter != "全部":
        df = df[df["is_returned"] == (returned_filter == "是")]
    if platform_filter != "全部":
        df = df[df["platform"] == platform_filter]
    df = format_order_df(df)
    st.dataframe(df)


# 2. 新增訂單

elif menu == "🧾 新增訂單":
    st.subheader("🧾 新增訂單")

    # --- 表單區塊 ---
    with st.form("add_order_form"):
        order_time      = st.date_input("下單日期", datetime.today())
        name            = st.text_input("客戶姓名")
        platform        = st.selectbox("下單平台", ["集運", "拼多多", "淘寶", "閒魚", "1688", "微店", "小紅書"])
        tracking_number = st.text_input("包裹單號")
        amount_rmb      = st.number_input("訂單金額（人民幣）", 0.0)
        service_fee     = st.number_input("代購手續費（NT$）", 0.0)
        weight_kg       = st.number_input("包裹公斤數", 0.0)
        is_arrived      = st.checkbox("已到貨")
        is_returned     = st.checkbox("已運回")
        remarks         = st.text_area("備註")

        # 送出按鈕
        submit = st.form_submit_button("✅ 新增訂單")

    # --- 按下送出後的處理 (與 with 同層) ---
    if submit:
        cursor.execute(
            """
            INSERT INTO orders 
              (order_time, customer_name, platform, tracking_number,
               amount_rmb, weight_kg, is_arrived, is_returned, service_fee, remarks)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (order_time, name, platform, tracking_number,
             amount_rmb, weight_kg, is_arrived, is_returned, service_fee, remarks)
        )
        conn.commit()

        # 建立一個可 later clear 的 placeholder
        notice = st.empty()
        notice.success("✅ 訂單已新增！")
        time.sleep(1)       # 顯示 1 秒
        notice.empty()      # 清掉訊息

       

# 3. 編輯訂單
elif menu == "✏️ 編輯訂單":
    st.subheader("✏️ 編輯訂單")

    # —— 四個獨立搜尋欄位 + 日期篩選 —— 
    id_search       = st.text_input("🔢 搜索訂單編號")
    name_search     = st.text_input("👤 搜索客戶姓名")
    amount_search   = st.text_input("💰 搜索訂單金額（人民幣）")
    tracking_search = st.text_input("📦 搜索包裹單號")
    date_search     = st.date_input("📅 搜索下單日期", value=None)
    returned_filter = st.selectbox("📦 是否已運回", ["全部", "✔ 已運回", "✘ 未運回"])


    # 動態組 SQL
    query  = "SELECT * FROM orders WHERE 1=1"
    params = []

    if id_search:
        query += " AND order_id = %s"
        params.append(int(id_search))
    if name_search:
        query += " AND customer_name LIKE %s"
        params.append(f"%{name_search}%")
    if amount_search:
        query += " AND amount_rmb = %s"
        params.append(float(amount_search))
    if tracking_search:
        query += " AND tracking_number LIKE %s"
        params.append(f"%{tracking_search}%")
    if date_search:
        query += " AND order_time = %s"
        params.append(date_search)
    if returned_filter == "✔ 已運回":
        query += " AND is_returned = 1"
    elif returned_filter == "✘ 未運回":
        query += " AND is_returned = 0"


    # 執行查詢
    df_raw = pd.read_sql(query, conn, params=params)

    if df_raw.empty:
        st.warning("⚠️ 查無任何訂單")
    else:
        # 顯示格式化後的表格
        df_show = format_order_df(df_raw.copy())
        st.dataframe(df_show)

        # 選擇要編輯的訂單編號
        edit_id = st.selectbox("選擇訂單編號", df_raw["order_id"].tolist())
        rec     = df_raw[df_raw["order_id"] == edit_id].iloc[0]

        # ===== 編輯表單 =====
        with st.form("edit_form"):
            order_time        = st.date_input("下單日期",     rec["order_time"])
            name              = st.text_input("客戶姓名",   rec["customer_name"])
            platform          = st.selectbox(
                                   "平台",
                                   ["集運","拼多多","淘寶","閒魚","1688","微店","小紅書"],
                                   index=["集運","拼多多","淘寶","閒魚","1688","微店","小紅書"]
                                         .index(rec["platform"])
                                )
            tracking_number   = st.text_input("包裹單號",    rec["tracking_number"])
            amount_rmb        = st.number_input("訂單金額（人民幣）", value=float(rec["amount_rmb"]))
            service_fee       = st.number_input("代購手續費（NT$）",   value=float(rec["service_fee"]))
            weight_kg         = st.number_input("包裹公斤數",       value=float(rec["weight_kg"]))
            is_arrived        = st.checkbox("已到貨",               value=bool(rec["is_arrived"]))
            is_returned       = st.checkbox("已運回",               value=bool(rec["is_returned"]))
            is_early_returned = st.checkbox("提前運回",             value=bool(rec.get("is_early_returned", False)))
            remarks           = st.text_area("備註",               rec["remarks"] or "")
            save              = st.form_submit_button("💾 儲存修改")

        # ===== 保存更新 =====
        if save:
            cursor.execute(
                """
                UPDATE orders SET
                  order_time        = %s,
                  customer_name     = %s,
                  platform          = %s,
                  tracking_number   = %s,
                  amount_rmb        = %s,
                  weight_kg         = %s,
                  is_arrived        = %s,
                  is_returned       = %s,
                  is_early_returned = %s,
                  service_fee       = %s,
                  remarks           = %s
                WHERE order_id      = %s
                """,
                (
                    order_time,
                    name,
                    platform,
                    tracking_number,
                    float(amount_rmb),
                    float(weight_kg),
                    bool(is_arrived),
                    bool(is_returned),
                    bool(is_early_returned),
                    float(service_fee),
                    remarks,
                    edit_id
                )
            )
            conn.commit()
            # 顯示 1 秒成功訊息後自動消失
            notice = st.empty()
            notice.success("✅ 訂單已更新！")
            time.sleep(1)
            notice.empty()

        # ===== 刪除按鈕 =====
        if st.button("🗑 刪除此訂單"):
            cursor.execute("DELETE FROM orders WHERE order_id = %s", (edit_id,))
            conn.commit()
            st.success("🗑 訂單已刪除！")

# 4. 搜尋訂單

elif menu == "🔍 搜尋訂單":
    st.subheader("🔍 搜尋訂單")

    # 用文字框搜文字／數字／單號
    kw_text = st.text_input("搜尋姓名/單號/金額/ID")
    # 用日期選擇器搜日期
    kw_date = st.date_input("搜尋下單日期", value=None)

    # 組 SQL
    query  = "SELECT * FROM orders WHERE 1=1"
    params = []

    if kw_text:
        query += " AND (customer_name LIKE %s OR tracking_number LIKE %s)"
        params += [f"%{kw_text}%", f"%{kw_text}%"]
        try:
            num = float(kw_text)
            query += " OR order_id = %s OR amount_rmb = %s"
            params += [int(num), num]
        except ValueError:
            pass

    if kw_date:
        query += " AND order_time = %s"
        params.append(kw_date)

    # 讀出結果
    df = pd.read_sql(query, conn, params=params)
    st.dataframe(format_order_df(df))


# 5. 可出貨名單
elif menu == "📦 可出貨名單":
    st.subheader("📦 可出貨名單")

    df_all = pd.read_sql("SELECT * FROM orders", conn)
    if df_all.empty:
        st.info("目前沒有任何訂單資料。")
    else:
        # 條件1：同一客戶所有訂單都已到貨
        arrived_all = df_all.groupby("customer_name")["is_arrived"].all()
        names_all_arrived = arrived_all[arrived_all].index.tolist()
        cond1 = df_all["customer_name"].isin(names_all_arrived)

        # 條件2：這筆訂單到貨且標記提前運回
        cond2 = (df_all["is_arrived"] == True) & (df_all["is_early_returned"] == True)

        # 排除「已運回」的訂單
        not_returned = df_all["is_returned"] == False

        # 最終篩選：符合 cond1 or cond2，且還沒運回
        df = df_all[(cond1 | cond2) & not_returned].copy()

        # 新增「單號後四碼」
        df["單號後四碼"] = df["tracking_number"].astype(str).str[-4:]

        # 中文化 + ✔/✘
        df = format_order_df(df)

        st.dataframe(df)

        # 下載按鈕
        towrite = io.BytesIO()
        df.to_excel(towrite, index=False, engine="openpyxl")
        towrite.seek(0)
        st.download_button(
            label="📥 下載可出貨名單.xlsx",
            data=towrite,
            file_name="可出貨名單.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# =====🚚 批次出貨=====

elif menu == "🚚 批次出貨":
    st.subheader("🚚 批次出貨")

    name = st.text_input("🔍 請輸入客戶姓名")
    if name.strip():
        # 查詢訂單
        df = pd.read_sql(
            "SELECT * FROM orders WHERE customer_name LIKE %s",
            conn,
            params=[f"%{name}%"]
        )

        if df.empty:
            st.warning("⚠️ 查無資料")
        else:
            # 顯示用表格（中文欄位＋✔✘）
            df_display = df.copy()
            column_mapping = {
                "order_id": "訂單編號",
                "order_time": "下單日期",
                "customer_name": "客戶姓名",
                "platform": "平台",
                "tracking_number": "包裹單號",
                "amount_rmb": "金額（人民幣）",
                "weight_kg": "公斤數",
                "is_arrived": "是否到貨",
                "is_returned": "是否已運回",
                "is_early_returned": "提前運回",
                "service_fee": "代購手續費",
                "remarks": "備註"
            }
            df_display = df_display.rename(columns=column_mapping)

            for col in ["是否到貨", "是否已運回", "提前運回"]:
                if col in df_display.columns:
                    df_display[col] = df_display[col].apply(lambda x: "✔" if x else "✘")

            # 顯示表格
            gb = GridOptionsBuilder.from_dataframe(df_display)
            gb.configure_selection("multiple", use_checkbox=True)
            grid_options = gb.build()

            grid_response = AgGrid(
                df_display,
                gridOptions=grid_options,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                fit_columns_on_grid_load=True,
                height=400,
                theme="material"
            )

            selected = grid_response["selected_rows"]

            # 加這兩行來印出實際內容與型別
            st.write("📋 選取類型:", type(selected))
            st.write("📋 選取內容:", selected)

            selected_ids = []

            # ➤ 判斷 selected 是 list 或 DataFrame，都能正確處理
            if isinstance(selected, list) and len(selected) > 0:
                selected_ids = [row["訂單編號"] for row in selected if isinstance(row, dict) and "訂單編號" in row]
            elif isinstance(selected, pd.DataFrame) and not selected.empty:
                selected_ids = selected["訂單編號"].tolist()

            if selected_ids:
                st.success(f"✅ 已選擇 {len(selected_ids)} 筆訂單")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("🚚 標記為『已運回』"):
                        try:
                            sql = f"UPDATE orders SET is_returned = 1 WHERE order_id IN ({','.join(['%s'] * len(selected_ids))})"
                            cursor.execute(sql, selected_ids)
                            conn.commit()
                            st.success("🚚 更新成功：已標記為『已運回』")
                        except Exception as e:
                            st.error(f"❌ 發生錯誤：{e}")

                with col2:
                    if st.button("📦 標記為『提前運回』"):
                        try:
                            sql = f"UPDATE orders SET is_early_returned = 1 WHERE order_id IN ({','.join(['%s'] * len(selected_ids))})"
                            cursor.execute(sql, selected_ids)
                            conn.commit()
                            st.success("📦 更新成功：已標記為『提前運回』")
                        except Exception as e:
                            st.error(f"❌ 發生錯誤：{e}")
            else:
                st.info("📋 請勾選欲標記的訂單")





# 6. 利潤報表/匯出

elif menu == "💰 利潤報表/匯出":
    st.subheader("💰 利潤報表與匯出")

    # 匯率輸入
    rmb_rate  = st.number_input("人民幣匯率", 0.0)
    sell_rate = st.number_input("定價匯率", 0.0)

    # 讀出所有訂單
    df = pd.read_sql("SELECT * FROM orders", conn)
    # 計算三個利潤欄位
    df["匯率價差利潤"]   = df["amount_rmb"] * (sell_rate - rmb_rate)
    df["代購手續費收入"] = df["service_fee"]
    df["總利潤"]       = df["匯率價差利潤"] + df["代購手續費收入"]

    # ----- 月份選擇器 -----
    df["order_time"] = pd.to_datetime(df["order_time"])
    years  = sorted(df["order_time"].dt.year.unique())
    year   = st.selectbox("選擇年份", years, index=len(years)-1)
    months = list(range(1,13))
    month  = st.selectbox("選擇月份", months, index=datetime.now().month-1)

    # 篩出該年月的訂單
    df_sel = df[(df["order_time"].dt.year == year) & (df["order_time"].dt.month == month)]
    st.markdown(f"#### {year} 年 {month} 月 訂單統計 （共 {len(df_sel)} 筆）")

    # 顯示 KPI
    col1, col2, col3 = st.columns(3)
    col1.metric("匯率價差利潤 (NT$)", f"{df_sel['匯率價差利潤'].sum():,.2f}")
    col2.metric("手續費收入 (NT$)",     f"{df_sel['代購手續費收入'].sum():,.2f}")
    col3.metric("總利潤 (NT$)",       f"{df_sel['總利潤'].sum():,.2f}")

    # 匯出該月報表
    st.markdown("### 📤 下載報表")
    df_export = df_sel.copy()
    df_export = format_order_df(df_export)  # 中文＋✔✘

    towrite = io.BytesIO()
    df_export.to_excel(towrite, index=False, engine="openpyxl")
    towrite.seek(0)
    st.download_button(
        label=f"📥 下載 {year}-{month:02d} 報表",
        data=towrite,
        file_name=f"代購利潤報表_{year}{month:02d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


