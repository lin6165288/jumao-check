import streamlit as st
import mysql.connector
import pandas as pd
import time
from datetime import datetime
import io
import re
import math
import json, os
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from feedback_store import init_db, read_feedbacks, update_status
init_db()


# ===== 入庫失敗佇列（純本機 JSON，無需改資料表） =====

QUEUE_FILE = "failed_inbound_queue.json"

def enqueue_failed(conn, tracking_number, weight_kg=None, raw_message=None, last_error=None):
    # 確保表存在（可留你原本的 ensure_* 寫法）
    ensure_failed_orders_table(conn)
    sql = """
    INSERT INTO failed_orders (tracking_number, weight_kg, raw_message, retry_count, last_error)
    VALUES (%s, %s, %s, 1, %s)
    ON DUPLICATE KEY UPDATE
      -- 只有當提供新值時才覆蓋，否則保留舊值
      weight_kg = IFNULL(VALUES(weight_kg), weight_kg),
      raw_message = IFNULL(VALUES(raw_message), raw_message),
      last_error = VALUES(last_error),
      retry_count = retry_count + 1,
      updated_at = CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(sql, (tracking_number, weight_kg, raw_message, last_error))
    conn.commit()



def ensure_failed_orders_table(conn):
    ddl = """
    CREATE TABLE IF NOT EXISTS failed_orders (
      id INT AUTO_INCREMENT PRIMARY KEY,
      tracking_number VARCHAR(64) NOT NULL,
      weight_kg DECIMAL(10,3) NULL,
      raw_message TEXT NULL,
      retry_count INT NOT NULL DEFAULT 0,
      last_error VARCHAR(255) NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      UNIQUE KEY uk_tracking (tracking_number)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()

def load_failed(conn):
    try:
        ensure_failed_orders_table(conn)
        with conn.cursor(dictionary=True) as cur:
            cur.execute("""
                SELECT tracking_number, weight_kg, raw_message, retry_count, last_error
                FROM failed_orders
                ORDER BY updated_at DESC
            """)
            rows = cur.fetchall()
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"讀取 failed_orders 發生錯誤：{e}")
        return pd.DataFrame(columns=["tracking_number","weight_kg","raw_message","retry_count","last_error"])


def clear_failed(conn):
    ensure_failed_orders_table(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE failed_orders")
    conn.commit()


def retry_failed_all(conn):
    df = load_failed(conn)
    success = fail = 0
    for _, row in df.iterrows():
        tn, w, raw_msg = row["tracking_number"], row["weight_kg"], row["raw_message"]
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE orders 
                    SET is_arrived = 1,
                        weight_kg = %s,
                        remarks = CONCAT(COALESCE(remarks,''), '｜自動入庫', NOW())
                    WHERE tracking_number = %s
                    """,
                    (w, tn)
                )
                if cur.rowcount > 0:
                    conn.commit()
                    with conn.cursor() as c2:
                        c2.execute("DELETE FROM failed_orders WHERE tracking_number=%s", (tn,))
                    conn.commit()
                    success += 1
                else:
                    enqueue_failed(conn, tn, w, raw_msg, "找不到對應訂單")
                    fail += 1
        except Exception as e:
            enqueue_failed(conn, tn, w, raw_msg, str(e))
            fail += 1
    return success, fail


def delete_failed_one(conn, tracking_number: str):
    """依 tracking_number 刪除 failed_orders 的單筆資料（唯一鍵）。"""
    ensure_failed_orders_table(conn)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM failed_orders WHERE tracking_number=%s LIMIT 1", (tracking_number,))
    conn.commit()


# ===
DELAY_TAG = "[延後]"

def has_delay_tag(x: str) -> bool:
    return (DELAY_TAG in str(x)) if x is not None else False

def add_delay_tag_sql(order_ids):
    # 在 remarks 前面加上 [延後] （若已存在則不重複）
    placeholders = ",".join(["%s"] * len(order_ids))
    sql = f"""
        UPDATE orders
        SET remarks = TRIM(
            CONCAT(
                '{DELAY_TAG} ',
                COALESCE(NULLIF(remarks,''), '')
            )
        )
        WHERE order_id IN ({placeholders})
          AND (remarks IS NULL OR remarks NOT LIKE %s)
    """
    params = [*order_ids, f"%{DELAY_TAG}%"]
    return sql, params

def remove_delay_tag_sql(order_ids):
    # 選用：移除 [延後] 標記
    placeholders = ",".join(["%s"] * len(order_ids))
    sql = f"""
        UPDATE orders
        SET remarks = TRIM(REPLACE(COALESCE(remarks,''), '{DELAY_TAG}', ''))
        WHERE order_id IN ({placeholders})
    """
    params = [*order_ids]
    return sql, params

#

def round_weight(w):
    if w < 0.1:
        return 0.1
    # math.ceil(x) * 0.05 會往上進位到最近的 0.05
    return round(math.ceil(w / 0.05) * 0.05, 2)

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
    "🔍 搜尋訂單", "📦 可出貨名單", "📥 貼上入庫訊息", "🚚 批次出貨", "💰 利潤報表/匯出", "💴 快速報價", "📮 匿名回饋管理"
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
            weight_val = rec["weight_kg"] if rec["weight_kg"] is not None else 0.0
            weight_kg  = st.number_input("包裹公斤數", value=float(weight_val))
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

        # ======== 原本名單（保留原顯示與整份下載） ========
        df["單號後四碼"] = df["tracking_number"].astype(str).str[-4:]
        df_show_all = format_order_df(df.copy())
        st.dataframe(df_show_all)

        towrite_full = io.BytesIO()
        df_show_all.to_excel(towrite_full, index=False, engine="openpyxl")
        towrite_full.seek(0)
        st.download_button(
            label="📥 下載可出貨名單.xlsx（全部）",
            data=towrite_full,
            file_name="可出貨名單.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.divider()

        # ======== 加：打勾只下載 + 延後運回（不改 DB 結構，用 remarks 的 [延後]） ========
        df["delayed_flag"] = df["remarks"].apply(has_delay_tag)

        df_display = format_order_df(df.copy())
        # 顯示延後標籤欄
        df_display.insert(1, "標記", df["delayed_flag"].map(lambda b: "⚠️ 延後" if b else ""))
        # 勾選欄
        if "✅ 選取" not in df_display.columns:
            df_display.insert(0, "✅ 選取", False)

        edited = st.data_editor(
            df_display,
            key="ready_editor",
            hide_index=True,
            disabled=[c for c in df_display.columns if c != "✅ 選取"],
            use_container_width=True,
            height=460,
            column_config={
                "✅ 選取": st.column_config.CheckboxColumn("✅ 選取", help="勾選要下載/延後的訂單"),
            },
        )

        picked_ids = df.loc[edited["✅ 選取"].values, "order_id"].tolist()

        c1, c2, c3 = st.columns(3)
        with c1:
            # 只匯出勾選名單
            buf = io.BytesIO()
            out_df = edited[edited["✅ 選取"] == True].drop(columns=["✅ 選取"]).copy()
            out_df.to_excel(buf, index=False, engine="openpyxl")
            buf.seek(0)
            st.download_button(
                "📥 下載可出貨名單（只含勾選）",
                data=buf,
                file_name="可出貨名單_只含勾選.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                disabled=len(picked_ids)==0,
                use_container_width=True
            )

        with c2:
            if st.button("⏰ 延後運回（標記勾選）", disabled=len(picked_ids)==0, use_container_width=True):
                try:
                    sql, params = add_delay_tag_sql(picked_ids)
                    cursor.execute(sql, params)
                    conn.commit()
                    st.success(f"已標記 {len(picked_ids)} 筆為【延後運回】。")
                    st.rerun()
                except Exception as e:
                    st.error(f"發生錯誤：{e}")

        with c3:
            # 選用：取消延後
            if st.button("🧹 取消延後（勾選）", disabled=len(picked_ids)==0, use_container_width=True):
                try:
                    sql2, params2 = remove_delay_tag_sql(picked_ids)
                    cursor.execute(sql2, params2)
                    conn.commit()
                    st.success(f"已移除 {len(picked_ids)} 筆的【延後】標記。")
                    st.rerun()
                except Exception as e:
                    st.error(f"發生錯誤：{e}")

        # ====== 原本統整：同客戶 包裹數 / 總公斤數 / 總國際運費（保留並加勾選/延後） ======
        st.markdown("### 📦 可出貨統整")

        df_calc = df_all[(cond1 | cond2) & not_returned].copy()
        df_calc["delayed_flag"] = df_calc["remarks"].apply(has_delay_tag)
        df_nonzero = df_calc[pd.to_numeric(df_calc["weight_kg"], errors="coerce").fillna(0) > 0].copy()

        # 依「客戶 × 平台」合併
        # 依「客戶 × 平台」合併（只統計本次清單中、重量>0 的訂單用於費用計算）
        grp = (
            df_nonzero
            .groupby(["customer_name", "platform"], as_index=False)
            .agg(total_w=("weight_kg", "sum"),
                 pkg_cnt=("order_id", "count"))   # 供參考，可不顯示
        )

        # 計價規則
        def billed_weight(w, pf):
            base = 1.0 if pf == "集運" else 0.5
            return max(base, math.ceil(float(w) / 0.5) * 0.5)
        
        def unit_price(pf):
            return 75.0 if pf == "集運" else 60.0

        grp["billed_w"]     = grp.apply(lambda r: billed_weight(r["total_w"], r["platform"]), axis=1)
        grp["price_per_kg"] = grp["platform"].apply(unit_price)
        grp["fee"]          = grp["billed_w"] * grp["price_per_kg"]

        # —— 新增：計算「本次清單」每位客戶的延後筆數 / 總筆數 —— 
        per_customer_delay = (
            df_calc.groupby("customer_name", as_index=False)
                   .agg(延後數=("delayed_flag", "sum"),
                        本次清單總筆數=("order_id", "count"))
        )

        # 客戶層級的費用彙總
        summary_fee = (
            grp.groupby("customer_name", as_index=False)
              .agg(包裹總數=("pkg_cnt", "sum"),
                    總公斤數=("total_w", "sum"),
                    總國際運費=("fee", "sum"))
        )

        # 合併「延後數/總筆數」資訊
        summary = summary_fee.merge(per_customer_delay, on="customer_name", how="left").fillna(0)

        # 產生標籤：0=無延後、全=全部延後、其他=部分延後
        def delay_label(row):
            d = int(row["延後數"])
            t = int(row["本次清單總筆數"])
            if t == 0 or d == 0:
                return ""                          # 沒有延後
            if d == t:
                return f"⛔ 全部延後（{d}/{t}）"
            return f"⚠️ 部分延後（{d}/{t}）"

        summary["標記"] = summary.apply(delay_label, axis=1)

        # 顯示用
        summary = summary.sort_values(["總國際運費", "總公斤數"], ascending=[False, False])

        summary_display = summary.copy()
        summary_display.rename(columns={"customer_name": "客戶姓名"}, inplace=True)

        # 你原本的勾選欄位
        summary_display.insert(0, "✅ 選取", False)

        # 把「標記」放在勾選後面，比較醒目
        cols = ["✅ 選取", "標記", "客戶姓名", "包裹總數", "本次清單總筆數", "延後數", "總公斤數", "總國際運費"]
        summary_display = summary_display[[c for c in cols if c in summary_display.columns]]

        edited_sum = st.data_editor(
            summary_display,
            key="summary_editor",
            hide_index=True,
            disabled=[c for c in summary_display.columns if c != "✅ 選取"],
            use_container_width=True,
            height=420,
            column_config={
                "✅ 選取": st.column_config.CheckboxColumn("✅ 選取", help="勾選要操作的客戶（只影響本次清單內的訂單）")
            }
        )

        picked_names = edited_sum.loc[edited_sum["✅ 選取"] == True, "客戶姓名"].tolist()

        only_nondelay = st.toggle("📄 匯出時排除延後（建議開啟）", value=True, help="勾選後，下載的可出貨名單只包含未標記『延後』的訂單。")


        cc0, cc1, cc2, cc3, cc4 = st.columns(5)

        
        with cc0:
            # 先取得本次清單中、屬於勾選客戶的訂單
            df_detail = df_calc[df_calc["customer_name"].isin(picked_names)].copy()
            if only_nondelay:
                df_detail = df_detail[~df_detail["delayed_flag"]].copy()

            # 沒資料就不要啟用下載鈕
            no_detail = (len(picked_names) == 0) or df_detail.empty

            # 用你的格式化函式輸出（與上方「可出貨名單」一致）
            df_detail_fmt = format_order_df(df_detail.copy())
        
            # 也可附上「單號後四碼」方便辨識（選擇性）
            if "tracking_number" in df_detail_fmt.columns and "單號後四碼" not in df_detail_fmt.columns:
                df_detail_fmt.insert(1, "單號後四碼", df_detail["tracking_number"].astype(str).str[-4:])

            # 下載（細項）
            buf_detail = io.BytesIO()
            df_detail_fmt.to_excel(buf_detail, index=False, engine="openpyxl")
            buf_detail.seek(0)

            st.download_button(
                "📥 下載可出貨名單（細項）",
                data=buf_detail,
                file_name=("可出貨名單_依勾選_排除延後.xlsx" if only_nondelay else "可出貨名單_依勾選_含延後.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                disabled=no_detail,
                use_container_width=True
            )

        # 下面保留你原本的四個按鈕（下載統整、延後、取消延後、標記已運回）
        with cc1:
            buf2 = io.BytesIO()
            out_sum = edited_sum[edited_sum["✅ 選取"]==True].drop(columns=["✅ 選取"]).copy()
            out_sum.to_excel(buf2, index=False, engine="openpyxl")
            buf2.seek(0)
            st.download_button(
                "📥 下載可出貨統整",
                data=buf2,
                file_name="可出貨統整_只含勾選.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                disabled=len(picked_names)==0,
                use_container_width=True
            )

        with cc2:
            if st.button("⏰ 延後運回 ", disabled=len(picked_names)==0, use_container_width=True):
                try:
                    ids = df_calc[df_calc["customer_name"].isin(picked_names)]["order_id"].tolist()
                    if ids:
                        sql, params = add_delay_tag_sql(ids)
                        cursor.execute(sql, params)
                        conn.commit()
                        st.success(f"已標記 {len(ids)} 筆訂單為【延後運回】。")
                        st.rerun()
                except Exception as e:
                    st.error(f"發生錯誤：{e}")

        with cc3:
            if st.button("🧹 取消延後運回 ", disabled=len(picked_names)==0, use_container_width=True):
                try:
                    ids = df_calc[df_calc["customer_name"].isin(picked_names)]["order_id"].tolist()
                    if ids:
                        sql2, params2 = remove_delay_tag_sql(ids)
                        cursor.execute(sql2, params2)
                        conn.commit()
                        st.success(f"已移除 {len(ids)} 筆的【延後】標記。")
                        st.rerun()
                except Exception as e:
                    st.error(f"發生錯誤：{e}")

        with cc4:
            if st.button("✅ 標記為已運回 ", disabled=len(picked_names)==0, use_container_width=True):
                try:
                    ids = df_calc[df_calc["customer_name"].isin(picked_names)]["order_id"].tolist()
                    if ids:
                        placeholders = ",".join(["%s"] * len(ids))
                        sql = f"UPDATE orders SET is_returned = 1 WHERE order_id IN ({placeholders})"
                        cursor.execute(sql, ids)
                        conn.commit()
                        st.success(f"✅ 已更新：{len(ids)} 筆訂單標記為『已運回』")
                        st.rerun()
                    else:
                        st.info("本次清單中沒有可更新的訂單。")
                except Exception as e:
                    st.error(f"❌ 發生錯誤：{e}")




# ========== 📥 貼上入庫訊息 → 自動更新 ==========

elif menu == "📥 貼上入庫訊息":
    st.subheader("📥 貼上入庫訊息 → 更新到貨狀態")

    raw = st.text_area(
        "把 LINE 官方帳號的入庫訊息整段貼上（可多則）",
        height=260,
        placeholder="例：\n順豐快遞SF3280813696247，入庫重量 0.14 KG\n中通快遞78935908059095，入庫重量 0.27 KG\n..."
    )

    # 解析樣式（沿用你原本的）
    patterns = [
        r'([A-Z]{1,3}\d{8,})[^0-9]*入庫重量\s*([0-9.]+)\s*KG',       # SF3280813696247 入庫重量 0.14 KG
        r'(\d{9,})[^0-9]*入庫重量\s*([0-9.]+)\s*KG',                 # 78935908059095 入庫重量 0.27 KG
        r'單號[:：]?\s*([A-Z0-9]{8,})[^0-9]*重量[:：]?\s*([0-9.]+)',  # 備用：單號xxx 重量x.xx
    ]

    # 進頁可選自動重試
    auto_retry = st.toggle("進入此頁時自動重試佇列", value=True)
    if auto_retry:
        ensure_failed_orders_table(conn)
        ok, fail = retry_failed_all(conn)
        if ok or fail:
            st.caption(f"🔁 自動重試：成功 {ok} 筆、仍待 {fail} 筆")
            
    if st.button("🔎 解析並更新"):
        found = []
        lines = raw.splitlines()
        for line in lines:
            t = line.strip()
            if not t:
                continue
            matched = None
            for p in patterns:
                m = re.search(p, t, flags=re.IGNORECASE)
                if m:
                    raw_w = float(m.group(2))
                    adj_w = round_weight(raw_w)  # ⚠️ 保留你原本的重量處理
                    matched = (m.group(1), adj_w, t)  # 加上原始訊息 t
                    break
            if matched:
                found.append(matched)

        if not found:
            st.warning("沒解析到任何『單號＋重量』，請確認範例格式或貼更多原文。")
        else:
            st.success(f"解析到 {len(found)} 筆：")
            st.write([(tn, w) for (tn, w, _) in found])

            
            
            # 寫回資料庫（一次計重；先找已有重量者，否則選最小 id）
            updated, missing = 0, []
            for tn, w, raw_line in found:
                # 只做最單純的查詢，避免各種 SQL 方言問題
                cursor.execute("""
                    SELECT id, weight_kg
                    FROM orders
                    WHERE tracking_number = %s
                """, (tn,))
                rows = cursor.fetchall()

                if not rows:
                    missing.append(tn)
                    enqueue_failed(conn, tn, w, raw_line, "找不到對應訂單")
                    continue

                # 取欄位的輔助：同時相容 DictCursor / Tuple cursor
                def _get_id(r):
                    try:
                        return r["id"]
                    except Exception:
                        return r[0]
                def _get_w(r):
                    try:
                        return r["weight_kg"]
                    except Exception:
                        return r[1]

                # 1) 先找「已經有重量」的那筆（>0 視為已計重）
                primary_row = None
                for r in rows:
                    rw = _get_w(r)
                    if rw is not None and float(rw) > 0:
                        primary_row = r
                        break

                if primary_row is not None:
                    primary_id = _get_id(primary_row)
                    primary_has_weight = True
                else:
                    # 2) 沒有已計重 → 選 id 最小者
                    ids = [_get_id(r) for r in rows]
                    primary_id = min(ids)
                    primary_has_weight = False

                # 3) 寫入主筆
                if primary_has_weight:
                    cursor.execute("""
                        UPDATE orders
                        SET is_arrived = 1,
                            remarks = CONCAT(COALESCE(remarks,''), '｜自動入庫(', NOW(), ') 主筆保留既有重量')
                        WHERE id = %s
                    """, (primary_id,))
                else:
                    cursor.execute("""
                        UPDATE orders
                        SET is_arrived = 1,
                            weight_kg = %s,
                            remarks = CONCAT(COALESCE(remarks,''), '｜自動入庫(', NOW(), ') 主筆=', %s, 'kg')
                        WHERE id = %s
                    """, (w, str(w), primary_id))

                # 4) 其他同單號 → 0kg + 已到倉
                cursor.execute("""
                    UPDATE orders
                    SET is_arrived = 1,
                        weight_kg = 0,
                        remarks = CONCAT(COALESCE(remarks,''), '｜自動入庫(', NOW(), ') 同單號=0kg')
                    WHERE tracking_number = %s
                      AND id <> %s
                """, (tn, primary_id))

                updated += 1

            conn.commit()
            


    # === 佇列檢視 / 操作 ===
    st.markdown("### 📨 未成功單號佇列")
    df_q = load_failed(conn)
    if not df_q.empty:
        st.caption(f"共有 {len(df_q)} 筆待重試")
    
        # 逐列顯示 + 單筆刪除
        for i, row in df_q.iterrows():
            tn = str(row["tracking_number"])
            w  = row.get("weight_kg", None)
            msg = row.get("raw_message", "")
            rc  = int(row.get("retry_count", 0))
            err = row.get("last_error", "")

            c1, c2, c3 = st.columns([7, 4, 1])
            with c1:
                st.markdown(f"**{tn}**｜入庫重量 **{w if w is not None else '—'} kg**")
                if msg:
                    st.caption(msg)
            with c2:
                st.write(f"重試次數：{rc}")
                st.write(f"最後錯誤：{err}")
            with c3:
                if st.button("🗑️", key=f"del_fail_{tn}_{i}", help="刪除此筆"):
                    delete_failed_one(conn, tn)
                    st.toast(f"已刪除：{tn}")
                    st.rerun()

        st.divider()
        c1, _, c3 = st.columns(3)
        with c1:
            if st.button("🔁 重試全部", use_container_width=True):
                ok, fail = retry_failed_all(conn)
                st.success(f"已重試：成功 {ok} 筆、仍待 {fail} 筆")
                st.rerun()
        with c3:
            if st.button("🧹 清空佇列", use_container_width=True):
                clear_failed(conn)
                st.warning("佇列已清空。")
                st.rerun()
    else:
        st.caption("目前沒有待重試的單號。")



# =====🚚 批次出貨=====

elif menu == "🚚 批次出貨":
    st.subheader("🚚 批次出貨")

    name = st.text_input("🔍 請輸入客戶姓名")
    if name.strip():
        # 1) 查詢訂單
        df = pd.read_sql(
            "SELECT * FROM orders WHERE customer_name LIKE %s",
            conn,
            params=[f"%{name}%"]
        )

        if df.empty:
            st.warning("⚠️ 查無資料")
        else:
            # 2) 顯示用表格（中文欄位 + ✔✘），保留「訂單編號」作為更新依據
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

            # 轉日期/空值，避免序列化問題
            if "下單日期" in df_display.columns:
                df_display["下單日期"] = pd.to_datetime(df_display["下單日期"], errors="coerce").dt.strftime("%Y-%m-%d")
            df_display = df_display.fillna("")

            # 布林欄位顯示為 ✔/✘（只影響顯示）
            for col in ["是否到貨", "是否已運回", "提前運回"]:
                if col in df_display.columns:
                    df_display[col] = df_display[col].apply(lambda x: "✔" if bool(x) else "✘")

            # 3) data_editor：加「✅ 選取」欄 / 只允許勾選該欄
            ui = df_display.copy()
            if "✅ 選取" not in ui.columns:
                ui.insert(0, "✅ 選取", False)

            disabled_cols = [c for c in ui.columns if c != "✅ 選取"]
            edited = st.data_editor(
                ui,
                key="batch_editor",
                hide_index=True,
                disabled=disabled_cols,          # 只讓「✅ 選取」能變動
                use_container_width=True,
                height=420,
            )

            # 4) 取得使用者勾選的「訂單編號」
            picked_ids = edited.loc[edited["✅ 選取"] == True, "訂單編號"].tolist()

            
            if picked_ids:
                sel = df["order_id"].isin(picked_ids)
                total_weight = pd.to_numeric(df.loc[sel, "weight_kg"], errors="coerce").fillna(0).sum()

                st.success(f"✅ 已選擇 {len(picked_ids)} 筆訂單，共 {total_weight:.2f} 公斤")

                c1, c2 = st.columns(2)

                with c1:
                    if st.button("🚚 標記為『已運回』"):
                        try:
                            placeholders = ",".join(["%s"] * len(picked_ids))
                            sql = f"UPDATE orders SET is_returned = 1 WHERE order_id IN ({placeholders})"
                            cursor.execute(sql, picked_ids)
                            conn.commit()
                        except Exception as e:
                            st.error(f"❌ 發生錯誤：{e}")
                        else:
                           st.success("🚚 更新成功：已標記為『已運回』")

                with c2:
                    if st.button("📦 標記為『提前運回』"):
                        try:
                            placeholders = ",".join(["%s"] * len(picked_ids))
                            sql = f"UPDATE orders SET is_early_returned = 1 WHERE order_id IN ({placeholders})"
                            cursor.execute(sql, picked_ids)
                            conn.commit()
                        except Exception as e:
                            st.error(f"❌ 發生錯誤：{e}")
                        else:
                            st.success("📦 更新成功：已標記為『提前運回』")
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

# 7. 快速報價
elif menu == "💴 快速報價":
    st.subheader("💴 快速報價小工具")

    rmb = st.number_input("商品價格（RMB）", min_value=0.00, step=0.01, format="%.2f")
    base_sell_rate = st.number_input("一般客戶匯率", value=4.6, step=0.01)
    vip_level = st.selectbox("VIP 等級", ["一般", "VIP1", "VIP2", "VIP3"])

    # ===== 計算邏輯 =====
    VIP_FEE_DISCOUNT = {"一般": 1.00, "VIP1": 0.90, "VIP2": 0.85, "VIP3": 0.80}
    MIN_FEE = 20  # 折扣後手續費下限

    def calc_base_fee(rmb: int) -> int:
        # 以 500 RMB 為級距：0~499→30；每多一個 500 → +50
        bin = rmb // 500
        return 30 if bin == 0 else bin * 50

    def quote_twd(rmb: int, level: str, rate: float) -> int:
        goods_ntd = rmb * rate
        base_fee = calc_base_fee(rmb)
        fee_after_discount = max(int(round(base_fee * VIP_FEE_DISCOUNT.get(level, 1.0))), MIN_FEE)
        return int(round(goods_ntd + fee_after_discount))

    if rmb > 0:
        total_ntd = quote_twd(rmb, vip_level, base_sell_rate)
        st.success(f"【報價單】\n商品價格：{rmb} RMB\n換算台幣價格：NT$ {total_ntd:,}")

        # ===== 一鍵複製：報價文字（自動帶入） =====

        # 折扣顯示文字（只負責顯示，不影響前面計算）
        discount_label_map = {"一般": "原價", "VIP1": "9 折", "VIP2": "85 折", "VIP3": "8 折"}
        discount_text = discount_label_map.get(vip_level, "原價")

        # 顯示用字串
        price_rmb = f"{rmb:.1f}".rstrip("0").rstrip(".")   # 150 -> "150", 150.0 -> "150"
        price_twd = f"{total_ntd:,}"                       # 12345 -> "12,345"

        quote_text = f"""【報價單】
 VIP 等級：{vip_level}（手續費 {discount_text}）
 商品價格：{price_rmb} RMB 
 換算台幣價格：{price_twd} 台幣 
 沒問題的話跟我說一聲～
 幫您扣款下單"""

        # 預覽（方便手動複製）
        st.text_area("要複製的內容（預覽）", value=quote_text, height=160)

        # —— 高相容一鍵複製（不使用 navigator.clipboard；不使用 f-string/.format）——
        import html as ihtml
        import streamlit.components.v1 as components

        escaped = ihtml.escape(quote_text).replace("\n", "&#10;")  # 保留換行
        html_block = (
            '''
            <div>
              <textarea id="copySrc" style="position:absolute;left:-9999px;top:-9999px">'''
            + escaped +
            '''</textarea>
              <button id="copyBtn" style="padding:8px 12px;border:none;border-radius:8px;cursor:pointer;">
                📋 一鍵複製
              </button>
              <script>
                const btn = document.getElementById('copyBtn');
                const ta  = document.getElementById('copySrc');
                btn.addEventListener('click', function () {
                  try {
                    ta.select();
                    ta.setSelectionRange(0, 999999); // iOS 相容
                    const ok = document.execCommand('copy');
                    btn.textContent = ok ? '✅ 已複製' : '❌ 複製失敗';
                  } catch (e) {
                    btn.textContent = '❌ 複製失敗';
                  }
                  setTimeout(() => btn.textContent = '📋 一鍵複製', 1500);
                });
              </script>
            </div>
            '''
        )
        components.html(html_block, height=60)



# "匿名回饋管理":
elif menu == "📮 匿名回饋管理":
    st.subheader("📮 匿名回饋管理")

    # 篩選列
    c1, c2, c3 = st.columns([2,1,1])
    with c1:
        keyword = st.text_input("關鍵字（內容／備註）", key="adm_kw")
    with c2:
        status = st.selectbox("狀態", ["全部","未處理","已讀","已回覆","忽略"], index=0, key="adm_status")
    with c3:
        if st.button("重新整理"):
            st.rerun()

    rows = read_feedbacks(keyword, status)
    df = pd.DataFrame(rows)
    st.caption(f"共 {0 if df.empty else len(df)} 筆")
    st.dataframe(
        df if not df.empty else pd.DataFrame(columns=["id","created_at","content","status","staff_note"]),
        use_container_width=True, hide_index=True
    )

    # 批次處理
    st.subheader("批次處理")
    ids_text = st.text_input("輸入要更新的 ID（逗號分隔）例：12,15,18", key="adm_ids")
    ids = [int(x) for x in ids_text.split(",") if x.strip().isdigit()] if ids_text else []

    cA, cB, cC = st.columns([1,1,2])
    with cA:
        new_status = st.selectbox("將狀態設為", ["已讀","已回覆","忽略"], key="adm_new_status")
    with cC:
        note = st.text_input("備註（選填，會覆蓋同欄位）", key="adm_note")
    with cB:
        if st.button("套用狀態"):
            if not ids:
                st.warning("請先輸入要更新的 ID")
            else:
                try:
                    update_status(ids, new_status, note or None)
                    st.success("已更新")
                    st.rerun()
                except Exception as e:
                    st.error(f"更新失敗：{e}")
    












































