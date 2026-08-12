import json
import os
import time
from datetime import datetime
import pandas as pd
import pytz
import requests
import streamlit as st
import yfinance as yf

# --- 從 stocks02.py 匯入清單 ---
from stocks02 import market_configs

st.set_page_config(page_title="全球股票監控", layout="wide")
st.markdown("#### 📊 全球股市即時監控 (線上編輯與區塊隔離)")

# 暫存檔名稱
ORDER_CACHE_FILE = "stock_order_cache.json"
USER_DATA_FILE = "user_custom_data.json"


# 1. 讀取與寫入「排序」暫存檔
def load_order_cache():
    if os.path.exists(ORDER_CACHE_FILE):
        try:
            with open(ORDER_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_order_cache(cache_data):
    try:
        with open(ORDER_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# 2. 讀取與寫入「用戶自訂數據」
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_user_data(user_data):
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# 3. 雙軌抓取即時股價
def get_stock_info(stock_dict):
    if not stock_dict:
        return pd.DataFrame()

    targets = []
    for code in stock_dict.keys():
        clean_code = str(code).split(".")[0]
        targets.append(f"tse_{clean_code}.tw")
        targets.append(f"otc_{clean_code}.tw")

    query_tickers = "|".join(targets)
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={query_tickers}&_={int(time.time()*1000)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }

    stock_data_map = {}
    try:
        res = requests.get(url, headers=headers, timeout=4)
        msg_array = res.json().get("msgArray", [])
        stock_data_map = {item["c"]: item for item in msg_array}
    except Exception:
        pass

    df_list = []
    for code, name in stock_dict.items():
        clean_code = str(code).split(".")[0]
        item = stock_data_map.get(clean_code)

        current_price = None
        change = None
        change_pct = None

        if item:
            try:
                price_str = item.get("z", "-")
                if price_str == "-":
                    price_str = item.get("b", "_").split("_")[0]
                if price_str == "-" or not price_str:
                    price_str = item.get("a", "_").split("_")[0]
                if price_str == "-" or not price_str:
                    price_str = item.get("y", "0")

                current_price = float(price_str)
                prev_close = float(item.get("y", 0))
                change = current_price - prev_close
                change_pct = (
                    (change / prev_close) * 100 if prev_close else 0
                )
            except Exception:
                pass

        if current_price is None:
            try:
                stock_obj = yf.Ticker(str(code))
                info = stock_obj.fast_info

                current_price = float(info["last_price"])
                prev_close = float(info["previous_close"])

                change = current_price - prev_close
                change_pct = (
                    (change / prev_close) * 100 if prev_close else 0
                )
            except Exception:
                pass

        df_list.append({
            "名稱": name,
            "股票代號": code,
            "當前價格": current_price,
            "漲跌": change,
            "漲跌幅(%)": change_pct,
        })

    return pd.DataFrame(df_list)


# 時間計算與快取載入
taipei_tz = pytz.timezone("Asia/Taipei")
now_taipei = datetime.now(taipei_tz).strftime("%Y-%m-%d %H:%M:%S")

saved_order_cache = load_order_cache()
saved_user_data = load_user_data()

tabs = st.tabs(list(market_configs.keys()))

# 垂直分隔線欄位名稱（使用不同隱藏空格保持 Key 唯一）
SEP1, SEP2, SEP3, SEP4, SEP5, SEP6 = (
    "│ ",
    "│  ",
    "│   ",
    "│    ",
    "│     ",
    "│      ",
)

for i, (market_name, stock_dict) in enumerate(market_configs.items()):
    with tabs[i]:
        # --- 頂部橫向佈局 ---
        col1, col2, col3 = st.columns([3, 2, 4], vertical_alignment="center")
        with col1:
            st.write(f"### **{market_name} 即時行情**")
        with col2:
            if st.button("🔄 點擊刷新價格", key=f"btn_refresh_{market_name}"):
                st.rerun()
        with col3:
            st.caption(f"⏱️ 最後更新時間 (台北): {now_taipei}")

        state_key = f"order_{market_name}"

        # 順序初始化
        if state_key not in st.session_state:
            if market_name in saved_order_cache:
                valid_saved_order = [
                    c for c in saved_order_cache[market_name] if c in stock_dict
                ]
                missing_codes = [
                    c for c in stock_dict.keys() if c not in valid_saved_order
                ]
                st.session_state[state_key] = valid_saved_order + missing_codes
            else:
                st.session_state[state_key] = list(stock_dict.keys())

        current_order = st.session_state[state_key]

        # ⚙️ 調整順序選單
        with st.expander("⚙️ 點擊展開：手動調整股票上下順序"):
            for idx, code in enumerate(current_order):
                col_name, col_up, col_down = st.columns([5, 1, 1])
                name = stock_dict.get(code, code)
                col_name.write(f"{idx + 1}. **{name}** (`{code}`)")

                if col_up.button("⬆️", key=f"up_{market_name}_{code}"):
                    if idx > 0:
                        (
                            current_order[idx],
                            current_order[idx - 1],
                        ) = (
                            current_order[idx - 1],
                            current_order[idx],
                        )
                        st.session_state[state_key] = current_order
                        saved_order_cache[market_name] = current_order
                        save_order_cache(saved_order_cache)
                        st.rerun()

                if col_down.button("⬇️", key=f"down_{market_name}_{code}"):
                    if idx < len(current_order) - 1:
                        (
                            current_order[idx],
                            current_order[idx + 1],
                        ) = (
                            current_order[idx + 1],
                            current_order[idx],
                        )
                        st.session_state[state_key] = current_order
                        saved_order_cache[market_name] = current_order
                        save_order_cache(saved_order_cache)
                        st.rerun()

        # 抓取即時行情
        ordered_dict = {
            code: stock_dict[code]
            for code in current_order
            if code in stock_dict
        }
        df_base = get_stock_info(ordered_dict)

        if not df_base.empty:
            rows = []
            for _, row in df_base.iterrows():
                code = row["股票代號"]
                u_data = saved_user_data.get(str(code), {})
                p = row["當前價格"]

                exp_sell = u_data.get("預期賣", None)
                last_sell = u_data.get("上次賣", None)
                sell_qty = u_data.get("賣出數量", None)
                exp_buy = u_data.get("預期買", None)
                buy_qty = u_data.get("買進數量", None)
                last_buy = u_data.get("上次買", None)
                last_buy_qty = u_data.get("上次買數量", None)
                cost = u_data.get("成本", None)
                hold_qty = u_data.get("持股數量", None)
                strategy = u_data.get("策略", "")

                # 綠色框百分比計算
                exp_sell_pct = (
                    ((p - exp_sell) / exp_sell * 100)
                    if (p and exp_sell)
                    else None
                )
                last_sell_pct = (
                    ((p - last_sell) / last_sell * 100)
                    if (p and last_sell)
                    else None
                )
                exp_buy_pct = (
                    ((exp_buy - p) / exp_buy * 100)
                    if (p and exp_buy)
                    else None
                )
                last_buy_pct = (
                    ((last_buy - p) / last_buy * 100)
                    if (p and last_buy)
                    else None
                )
                cost_pct = (
                    ((p - cost) / cost * 100) if (p and cost) else None
                )

                # 按區塊順序組裝資料並插入分隔線 (│)
                rows.append({
                    "名稱": row["名稱"],
                    "股票代號": row["股票代號"],
                    "當前價格": row["當前價格"],
                    "漲跌": row["漲跌"],
                    "漲跌幅(%)": row["漲跌幅(%)"],
                    SEP1: "│",
                    "預期賣": (
                        float(exp_sell) if exp_sell is not None else None
                    ),
                    "與現價%(賣)": exp_sell_pct,
                    SEP2: "│",
                    "上次賣": (
                        float(last_sell) if last_sell is not None else None
                    ),
                    "與現價%(上次賣)": last_sell_pct,
                    "賣出數量": (
                        int(sell_qty) if sell_qty is not None else None
                    ),
                    SEP3: "│",
                    "預期買": (
                        float(exp_buy) if exp_buy is not None else None
                    ),
                    "與現價%(買)": exp_buy_pct,
                    "買進數量": (
                        int(buy_qty) if buy_qty is not None else None
                    ),
                    SEP4: "│",
                    "上次買": (
                        float(last_buy) if last_buy is not None else None
                    ),
                    "與現價%(上次買)": last_buy_pct,
                    "上次買數量": (
                        int(last_buy_qty) if last_buy_qty is not None else None
                    ),
                    SEP5: "│",
                    "成本": float(cost) if cost is not None else None,
                    "與現價%(成本)": cost_pct,
                    "持股數量": (
                        int(hold_qty) if hold_qty is not None else None
                    ),
                    SEP6: "│",
                    "策略": strategy,
                })

            full_df = pd.DataFrame(rows)

            # 禁用編輯的欄位包含基本行情、計算欄位與分隔線欄位
            disabled_cols = [
                "名稱",
                "股票代號",
                "當前價格",
                "漲跌",
                "漲跌幅(%)",
                "與現價%(賣)",
                "與現價%(上次賣)",
                "與現價%(買)",
                "與現價%(上次買)",
                "與現價%(成本)",
                SEP1,
                SEP2,
                SEP3,
                SEP4,
                SEP5,
                SEP6,
            ]

            # 分隔欄設定 (設為極窄且標頭顯示為 │)
            sep_config = st.column_config.Column("│", width="extra_small")

            edited_df = st.data_editor(
                full_df,
                disabled=disabled_cols,
                column_config={
                    "當前價格": st.column_config.NumberColumn(format="%.2f"),
                    "漲跌": st.column_config.NumberColumn(format="%.2f"),
                    "漲跌幅(%)": st.column_config.NumberColumn(format="%.2f%%"),
                    "與現價%(賣)": st.column_config.NumberColumn(
                        format="%.1f%%"
                    ),
                    "與現價%(上次賣)": st.column_config.NumberColumn(
                        format="%.1f%%"
                    ),
                    "與現價%(買)": st.column_config.NumberColumn(
                        format="%.1f%%"
                    ),
                    "與現價%(上次買)": st.column_config.NumberColumn(
                        format="%.1f%%"
                    ),
                    "與現價%(成本)": st.column_config.NumberColumn(
                        format="%.1f%%"
                    ),
                    SEP1: sep_config,
                    SEP2: sep_config,
                    SEP3: sep_config,
                    SEP4: sep_config,
                    SEP5: sep_config,
                    SEP6: sep_config,
                    "策略": st.column_config.SelectboxColumn(
                        options=["", "買進", "賣出", "觀望", "加碼"]
                    ),
                },
                use_container_width=True,
                height=350,
                key=f"editor_{market_name}",
            )

            # 檢測使用者編輯並自動寫入 JSON
            has_changed = False
            for _, r in edited_df.iterrows():
                code = str(r["股票代號"])
                old_entry = saved_user_data.get(code, {})

                new_entry = {
                    "預期賣": r["預期賣"],
                    "上次賣": r["上次賣"],
                    "賣出數量": r["賣出數量"],
                    "預期買": r["預期買"],
                    "買進數量": r["買進數量"],
                    "上次買": r["上次買"],
                    "上次買數量": r["上次買數量"],
                    "成本": r["成本"],
                    "持股數量": r["持股數量"],
                    "策略": r["策略"],
                }

                new_entry = {
                    k: v
                    for k, v in new_entry.items()
                    if pd.notna(v) and v != ""
                }

                if old_entry != new_entry:
                    saved_user_data[code] = new_entry
                    has_changed = True

            if has_changed:
                save_user_data(saved_user_data)
                st.rerun()

st.caption("💡 提示：表格中已加入 `│` 垂直欄位隔開行情、買賣策略與成本區塊。")
