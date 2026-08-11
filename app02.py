import time

def get_twse_stock_info(stock_dict):
    if not stock_dict:
        return pd.DataFrame()
    
    # 1. 同時產生 tse (上市) 與 otc (上櫃) 的查詢字串
    targets = []
    for code in stock_dict.keys():
        targets.append(f"tse_{code}.tw")
        targets.append(f"otc_{code}.tw")
    
    query_tickers = "|".join(targets)
    # 加上 timestamp 避免證交所快取或阻擋
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={query_tickers}&_={int(time.time()*1000)}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        msg_array = res.json().get('msgArray', [])
        
        # 整理抓到的資料
        stock_data_map = {}
        for item in msg_array:
            stock_data_map[item['c']] = item
    except Exception:
        stock_data_map = {}

    df_list = []
    for code, name in stock_dict.items():
        item = stock_data_map.get(str(code))
        
        if item:
            try:
                # 盤後或未成交時 z 會是 "-"，依序向買價(b)、賣價(a)、昨收(y) 取值備援
                price_str = item.get('z', '-')
                if price_str == '-':
                    price_str = item.get('b', '_').split('_')[0] # 買價
                if price_str == '-' or not price_str:
                    price_str = item.get('a', '_').split('_')[0] # 賣價
                if price_str == '-' or not price_str:
                    price_str = item.get('y', '0')              # 昨收價
                
                current_price = float(price_str)
                prev_close = float(item['y'])
                
                change = current_price - prev_close
                change_pct = (change / prev_close) * 100 if prev_close else 0
                
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
