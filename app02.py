import time
from datetime import datetime
import pandas as pd
import pytz
import requests
import streamlit as st
import yfinance as yf

# --- 從 stocks.py 匯入清單 ---
from stocks import market_configs

st.set_page_config(page_title="全球股票監控", layout="wide")
st.markdown("#### 📊 全球股市即時監控 (雙軌智慧模式)")


def get_stock_info(stock_dict):
    if not stock_dict:
        return pd.DataFrame()

    # 1. 整理清單，去除 .TW / .TWO 產出 TWSE 查詢字串
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

    # 先用 TWSE API 批次抓取台股上市上櫃資料
    stock_data_map = {}
    try:
        res = requests.get(url, headers=headers, timeout=4)
        msg_array = res.json().get("msgArray", [])
        stock_data_map = {item["c"]: item for item in msg_array}
    except Exception:
        pass

    df_list = []
    # 按照傳入 stock_dict 的順序讀取
    for code, name in stock_dict.items():
        clean_code = str(code).split(".")[0]
        item = stock_data_map.get(clean_code)

        current_price = None
        change = None
        change_pct = None

        # 軌道 A: TWSE API 成功抓到上市/上櫃資料
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

        # 軌道 B: 若 TWSE 抓不到 (興櫃股票、陸股、美股等)，自動改用 yfinance
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


# 分頁與表格渲染
tabs = st.tabs(list(market_configs.keys()))

for i, (market_name, stock_dict) in enumerate(market_configs.items()):
    with tabs[i]:
        st.write(f"**{market_name} 即時行情**")

        # 功能 1：手動調整與篩選股票排列順序
        ordered_codes = st.multiselect(
            "↕️ 手動調整股票順序 (可拖曳或重新點選)：",
            options=list(stock_dict.keys()),
            default=list(stock_dict.keys()),
            key=f"select_{market_name}",
        )

        # 依使用者調整後的順序重建字典
        filtered_dict = {
            code: stock_dict[code]
            for code in ordered_codes
            if code in stock_dict
        }

        df = get_stock_info(filtered_dict)

        if not df.empty:

            def color_change(val):
                try:
                    if val > 0:
                        return "color: #ff4b4b;"  # 紅漲
                    elif val < 0:
                        return "color: #008000;"  # 綠跌
                except:
                    pass
                return ""

            market_upper = market_name.upper()
            if any(k in market_upper for k in ["中國", "CN", "美國", "US"]):
                price_format = "{:.3f}"
            else:
                price_format = "{:.2f}"

            # 功能 2：st.dataframe 原生支援直接點擊標頭欄位排序 (數字/文字)
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

# 時間顯示
taipei_tz = pytz.timezone("Asia/Taipei")
now_taipei = datetime.now(taipei_tz).strftime("%Y-%m-%d %H:%M:%S")

st.caption(f"最後更新時間 (台北): {now_taipei}")
st.caption(
    "💡 提示：點擊表格標題欄位可自動排序；使用上方多選框可手動拖曳變更股票顯示順序。"
)

if st.button("🔄 點擊刷新價格"):
    st.rerun()
