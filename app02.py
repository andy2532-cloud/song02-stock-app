import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
# --- 從 stocks02.py 匯入清單 ---
from stocks02 import market_configs

st.set_page_config(page_title="全球股票監控", layout="wide")
st.markdown("#### 📊 全球股市即時監控 (TWSE API 模式)")

def get_twse_stock_info(stock_dict):
    if not stock_dict:
        return pd.DataFrame()
    
    # 將代號組合成 TWSE 要求的格式，例如: tse_2330.tw|tse_2317.tw
    # 支援上市 (tse) 與 上櫃 (otc)，可統一先用 tse 或同時查詢
    query_tickers = "|".join([f"tse_{code}.tw" for code in stock_dict.keys()])
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={query_tickers}"
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()
        msg_array = data.get('msgArray', [])
        
        # 轉成字典以便快速對照: {'2330': {資料...}}
        stock_data_map = {item['c']: item for item in msg_array}
    except Exception as e:
        stock_data_map = {}

    df_list = []
    for code, name in stock_dict.items():
        item = stock_data_map.get(str(code))
        
        if item:
            try:
                # z: 最近成交價, y: 昨收價
                # 若盤前未成交，z 可能為 '-'，可退而取最佳叫買價 b
                current_price = float(item['z']) if item.get('z') != '-' else float(item['b'].split('_')[0])
                prev_close = float(item['y'])
                
                change = current_price - prev_close
                change_pct = (change / prev_close) * 100
                
                df_list.append({
                    "名稱": name,
                    "股票代號": code,
                    "當前價格": current_price,
                    "漲跌": change,
                    "漲跌幅(%)": change_pct
                })
            except (ValueError, KeyError, IndexError):
                df_list.append({"名稱": name, "股票代號": code, "當前價格": None, "漲跌": None, "漲跌幅(%)": None})
        else:
            df_list.append({"名稱": name, "股票代號": code, "當前價格": None, "漲跌": None, "漲跌幅(%)": None})

    return pd.DataFrame(df_list)

# 頁面與表格渲染
tabs = st.tabs(list(market_configs.keys()))

for i, (market_name, stock_dict) in enumerate(market_configs.items()):
    with tabs[i]:
        st.write(f"**{market_name} 即時行情**")
        df = get_twse_stock_info(stock_dict)
        
        if not df.empty:
            def color_change(val):
                try:
                    if val > 0: return 'color: #ff4b4b;' # 紅漲
                    elif val < 0: return 'color: #008000;' # 綠跌
                except: pass
                return ''

            st.dataframe(
                df.style.map(color_change, subset=['漲跌', '漲跌幅(%)'])
                .format("{:.2f}", subset=['當前價格', '漲跌', '漲跌幅(%)'], na_rep="-"),
                use_container_width=True,
                height=300
            )

# 時間顯示
taipei_tz = pytz.timezone('Asia/Taipei')
now_taipei = datetime.now(taipei_tz).strftime('%Y-%m-%d %H:%M:%S')

st.caption(f"最後更新時間 (台北): {now_taipei}")
st.caption("註：資料來源為臺灣證券交易所 (TWSE MIS)。")

if st.button('🔄 點擊刷新價格'):
    st.rerun()
