import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz
# --- 重點：從 stocks.py 匯入清單 ---
from stocks import market_configs

# 設定網頁標題
st.set_page_config(page_title="全球股票-02", layout="wide")

# 1. 調整標題大小
st.markdown("#### 📊 全球股市即時監控02 (Excel 模式)")

def get_stock_info(stock_dict):
    if not stock_dict:
        return pd.DataFrame()
    
    df_list = []
    for ticker, name in stock_dict.items():
        try:
            stock_obj = yf.Ticker(ticker)
            info = stock_obj.fast_info
            
            current_price = info['last_price']
            prev_close = info['previous_close']
            
            if prev_close is None or prev_close == 0:
                prev_close = stock_obj.info.get('previousClose', current_price)
            
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100
            
            df_list.append({
                "名稱": name,
                "股票代號": ticker,
                "當前價格": float(current_price),
                "漲跌": float(change),
                "漲跌幅(%)": float(change_pct)
            })
        except:
            df_list.append({"名稱": name, "股票代號": ticker, "當前價格": None, "漲跌": None, "漲跌幅(%)": None})
    
    return pd.DataFrame(df_list)

# 2. 建立 Excel 分頁
tabs = st.tabs(list(market_configs.keys()))

for i, (market_name, stock_dict) in enumerate(market_configs.items()):
    with tabs[i]:
        st.write(f"**{market_name} 即時行情**")
        df = get_stock_info(stock_dict)
        
        if not df.empty:
            def color_change(val):
                try:
                    if val > 0: return 'color: #ff4b4b;'
                    elif val < 0: return 'color: #008000;'
                except: pass
                return ''

            st.dataframe(
                df.style.map(color_change, subset=['漲跌', '漲跌幅(%)'])
                .format("{:.2f}", subset=['當前價格', '漲跌', '漲跌幅(%)'], na_rep="-"),
                use_container_width=True,
                height=300
            )

# 3. 處理台北時間
taipei_tz = pytz.timezone('Asia/Taipei')
now_taipei = datetime.now(taipei_tz).strftime('%Y-%m-%d %H:%M:%S')

st.caption(f"最後更新時間 (台北): {now_taipei}")
st.caption("註：免費數據通常有 15 分鐘延遲。")

if st.button('🔄 點擊刷新價格'):
    st.rerun()
