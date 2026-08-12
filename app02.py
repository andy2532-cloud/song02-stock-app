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
st.markdown("#### 📊 全球股市即時監控 (雙軌智慧模式)")

# 暫存檔名稱
CACHE_FILE = "stock_order_cache.json"


# 讀取暫存檔
def load_order_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


# 寫入暫存檔
def save_order_cache(cache_data):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


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


# 取得台北目前時間
taipei_tz = pytz.timezone("Asia/Taipei")
now_taipei = datetime.now(taipei_tz).strftime("%Y-%m-%d %H:%M:%S")

# 載入歷史儲存順序
saved_cache = load_order_cache()

tabs = st.tabs(list(market_configs.keys()))

for i, (market_name, stock_dict) in enumerate(market_configs.items()):
    with tabs[i]:
        # --- 頂部橫向整排佈局 (標題 | 刷新按鈕 | 最後更新時間) ---
        col1, col2, col3 = st.columns([3, 2, 4], vertical_alignment="center")

        with col1:
            st.write(f"### **{market_name} 即時行情**")

        with col2:
            if st.button("🔄 點擊刷新價格", key=f"btn_refresh_{market_name}"):
                st.rerun()

        with col3:
            st.caption(f"⏱️ 最後更新時間 (台北): {now_taipei}")

        state_key = f"order_{market_name}"

        # 首次載入：優先讀取 JSON 暫存檔
        if state_key not in st.session_state:
            if market_name in saved_cache:
                valid_saved_order = [
                    c for c in saved_cache[market_name] if c in stock_dict
                ]
                missing_codes = [
                    c for c in stock_dict.keys() if c not in valid_saved_order
                ]
                st.session_state[state_key] = valid_saved_order + missing_codes
            else:
                st.session_state[state_key] = list(stock_dict.keys())

        current_order = st.session_state[state_key]

        # ⚙️ 調整選單
        with st.expander("⚙️ 點擊展開：手動調整股票上下順序 (自動存檔)"):
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
                        saved_cache[market_name] = current_order
                        save_order_cache(saved_cache)
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
                        saved_cache[market_name] = current_order
                        save_order_cache(saved_cache)
                        st.rerun()

        # 依順序讀取資料
        ordered_dict = {
            code: stock_dict[code]
            for code in current_order
            if code in stock_dict
        }

        df = get_stock_info(ordered_dict)

        if not df.empty:

            def color_change(val):
                try:
                    if val > 0:
                        return "color: #ff4b4b;"
                    elif val < 0:
                        return "color: #008000;"
                except:
                    pass
                return ""

            market_upper = market_name.upper()
            if any(k in market_upper for k in ["中國", "CN", "美國", "US"]):
                price_format = "{:.3f}"
            else:
                price_format = "{:.2f}"

            st.dataframe(
                df.style.map(color_change, subset=["漲跌", "漲跌幅(%)"])
                .format(
                    price_format,
                    subset=["當前價格", "漲跌", "漲跌幅(%)"],
                    na_rep="-",
                ),
                use_container_width=True,
                height=300,
            )

st.caption(
    "💡 提示：點擊「手動調整股票上下順序」可調整位置；點擊表格標頭可快速按數字大小排序。"
)
