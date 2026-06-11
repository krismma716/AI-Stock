import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 🚀 初始設定：寬螢幕模式
st.set_page_config(page_title="AI 專業看盤終端 (2026 升級版)", layout="wide", initial_sidebar_state="collapsed")

# --- 0. 全局風格設定 ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&display=swap');
.stApp { background-color: #0d1117 !important; font-family: 'Noto Sans TC', sans-serif; }
[data-testid="stSidebar"] { display: none; }
header {visibility: hidden;} footer {visibility: hidden;}
div.block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; max-width: 98% !important; }
.top-nav-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.stTextInput input { background-color: #161b22 !important; color: #fff !important; border: 1px solid #30363d !important; border-radius: 4px; padding: 4px 8px; height: 32px; font-size: 13px;}
button[kind="primary"] { background-color: #f85149 !important; color: #fff !important; border: none !important; border-radius: 4px !important; width: 100%; font-weight: bold; height: 32px; transition: 0.2s; padding: 0; font-size: 13px;}
button[kind="primary"]:hover { background-color: #d13b35 !important; }
button[kind="secondary"] { background-color: #21262d !important; color: #c9d1d9 !important; border: 1px solid #30363d !important; border-radius: 4px !important; transition: 0.2s; padding: 2px 10px !important; font-size: 12px !important; height: 28px !important;}
button[kind="secondary"]:hover { background-color: #30363d !important; border-color: #8b949e !important; color: #fff !important; }
.stTabs [data-baseweb="tab-list"] { gap: 2px; background-color: transparent; padding: 0; border-bottom: 1px solid #30363d; margin-bottom: 5px; }
.stTabs [data-baseweb="tab"] { background-color: transparent; border: none; padding: 4px 10px; color: #8b949e; font-size: 12px;}
.stTabs [aria-selected="true"] { color: #58a6ff !important; border-bottom: 2px solid #58a6ff !important; background-color: transparent !important; }
.d-card { background:#161b22; padding:12px; border-radius:6px; border:1px solid #30363d; margin-bottom:10px; box-shadow: 0 2px 6px rgba(0,0,0,0.3); }
.d-title { font-size:14px; font-weight:900; color:#fff; border-bottom:1px solid #30363d; padding-bottom:4px; margin-bottom:8px; }
.g-2 { display:grid; grid-template-columns:repeat(2, 1fr); gap:8px; }
.g-3 { display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; }
.g-4 { display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; }
.m-box { background:#21262d; padding:8px; border-radius:4px; border:1px solid #30363d; }
.m-title { font-size:10px; color:#8b949e; margin-bottom:2px; text-transform:uppercase;}
.m-val { font-size:16px; font-weight:900; color:#fff; line-height:1.2; }
.text-red { color:#f85149 !important; } .text-green { color:#3fb950 !important; } .text-white { color:#fff !important; } .text-yellow { color:#d29922 !important; }
details > summary { list-style: none; outline: none; cursor: pointer; padding: 2px; transition: 0.2s; display: flex; align-items: center; color: #c9d1d9; font-size: 12px;}
details > summary::-webkit-details-marker { display: none; }
details > summary:hover { color: #fff; }
.info-box { padding: 6px 10px; margin: 2px 0 6px 20px; background: rgba(88, 166, 255, 0.08); border-left: 2px solid #58a6ff; font-size: 11px; color: #8b949e; }
.dotted-link { text-decoration: underline dotted #8b949e; text-underline-offset: 3px; margin-left: 6px; }
</style>
""", unsafe_allow_html=True)

if 'history' not in st.session_state: st.session_state['history'] = [("2330", "台積電")] 
if 'target' not in st.session_state: st.session_state['target'] = "2330"

def get_consecutive_days(series):
    if len(series) == 0: return 0
    vals = series.values[::-1] 
    if vals[0] == 0: return 0
    is_buy = vals[0] > 0
    count = 0
    for v in vals:
        if (v > 0 and is_buy) or (v < 0 and not is_buy): count += 1
        else: break
    return count if is_buy else -count

def safe_float(val, is_pct=False):
    if val is None or pd.isna(val) or val == '-': return "-"
    try: 
        v = float(val)
        if is_pct:
            if v > 0.3: return "-" 
            return f"{v*100:.2f}%"
        return f"{v:.2f}"
    except: return "-"

@st.cache_data(ttl=3600) 
def get_chinese_name(stock_id):
    clean_id = stock_id.replace('.TW', '').replace('.TWO', '')
    try:
        res = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo&data_id={clean_id}", timeout=3).json()
        if res.get('msg') == 'success' and len(res.get('data', [])) > 0: return res['data'][0]['stock_name']
    except: pass
    return None

# --- 1. 資料與指標運算 ---
@st.cache_data(ttl=60) 
def get_data(stock_id):
    tk = f"{stock_id}.TWO" if not stock_id.endswith(('.TW','.TWO')) else stock_id
    tk_obj = yf.Ticker(tk)
    
    try:
        df = tk_obj.history(period="1y")
        if df.empty:
            tk = f"{stock_id}.TW"
            tk_obj = yf.Ticker(tk)
            df = tk_obj.history(period="1y")
            if df.empty: return (None,) * 10
    except Exception as e:
        print(f"Yahoo Data Error: {e}")
        return (None,) * 10
        
    df.index = df.index.tz_localize(None)

    df_intra = None
    try:
        df_intra = tk_obj.history(period="1d", interval="1m")
        if not df_intra.empty and df_intra.index.tz is not None:
            df_intra.index = df_intra.index.tz_convert('Asia/Taipei').tz_localize(None)
    except: pass

    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{tk}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    live_price, prev_close, quote_time = None, None, "抓取中..."
    try:
        res = requests.get(url, headers=headers, timeout=5).json()
        meta = res['chart']['result'][0]['meta']
        live_price = float(meta['regularMarketPrice'])
        prev_close = float(meta['chartPreviousClose'])
        dt_utc = datetime.datetime.utcfromtimestamp(meta['regularMarketTime'])
        quote_time = (dt_utc + datetime.timedelta(hours=8)).strftime('%H:%M:%S')
    except Exception: pass
        
    if live_price is None:
        live_price = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else live_price
        quote_time = "歷史資料"

    tw_now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    tw_today = tw_now.date()
    if df.index[-1].date() < tw_today and tw_now.hour >= 9 and tw_now.weekday() < 5:
        df.loc[pd.to_datetime(tw_today)] = {'Open': live_price, 'High': live_price, 'Low': live_price, 'Close': live_price, 'Volume': 0}
    df.iloc[-1, df.columns.get_loc('Close')] = live_price

    df['MA7'] = df['Close'].rolling(7).mean()
    df['MA14'] = df['Close'].rolling(14).mean()
    df['MA21'] = df['Close'].rolling(21).mean() 
    df['MA35'] = df['Close'].rolling(35).mean() 
    df['STD21'] = df['Close'].rolling(21).std()
    df['BBU'] = df['MA21'] + (2 * df['STD21'])
    df['BBL'] = df['MA21'] - (2 * df['STD21'])
    df['Resist'] = df['High'].shift(1).rolling(21).max()
    df['Support'] = df['Low'].shift(1).rolling(21).min()
    
    delta = df['Close'].diff()
    df['RSI'] = 100 - (100 / (1 + (delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean() / -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean())))
    df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
    df['MACD_S'] = df['MACD'].ewm(span=9).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_S']
    low_min, high_max = df['Low'].rolling(9).min(), df['High'].rolling(9).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['K'] = rsv.ewm(com=2, adjust=False).mean() 
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()

    df['VMA7'] = df['Volume'].rolling(7).mean()
    df['Vol_Ratio'] = df['Volume'] / df['VMA7']
    df['OBV'] = (np.sign(delta) * df['Volume']).fillna(0).cumsum()
    df['OBV_MA14'] = df['OBV'].rolling(14).mean()

    df = df.dropna()
    stock_name = get_chinese_name(stock_id) or stock_id
    
    # 🎯 修復順序：先抓取 info
    try: info = tk_obj.info
    except: info = {}
    
    # 🎯 修復順序：再強制計算殖利率，並直接寫入剛剛抓到的 info 裡
    try:
        divs = tk_obj.dividends
        if not divs.empty:
            one_year_ago = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
            ttm_div = divs[divs.index >= one_year_ago].sum()
            if ttm_div > 0 and live_price > 0:
                # 這裡強制把算好的真實殖利率塞給 info
                info['dividendYield'] = float(ttm_div / live_price) 
    except Exception as e:
        print(f"Dividend Calc Error: {e}")

    start_date = (tw_now - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    clean_id = stock_id.replace('.TW', '').replace('.TWO', '')
    chips_url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestorsBuySell&data_id={clean_id}&start_date={start_date}"
    
    chips_data = {"f_buy_5d": 0, "t_buy_5d": 0, "f_consec": 0, "t_consec": 0, "status": "fail"}
    try:
        res = requests.get(chips_url, headers=headers, timeout=5).json()
        if res.get('msg') == 'success' and len(res.get('data', [])) > 0:
            df_chips = pd.DataFrame(res['data'])
            df_chips['buy'], df_chips['sell'] = pd.to_numeric(df_chips['buy'], errors='coerce').fillna(0), pd.to_numeric(df_chips['sell'], errors='coerce').fillna(0)
            df_chips['net_buy'] = (df_chips['buy'] - df_chips['sell']) / 1000 
            f_mask, t_mask = df_chips['name'].str.contains('Foreign', case=False, na=False), df_chips['name'].str.contains('Trust', case=False, na=False)
            df_f, df_t = df_chips[f_mask].groupby('date')['net_buy'].sum().sort_index(), df_chips[t_mask].groupby('date')['net_buy'].sum().sort_index()
            if not df_f.empty or not df_t.empty:
                chips_data = {"f_buy_5d": int(df_f.tail(5).sum()) if not df_f.empty else 0, "t_buy_5d": int(df_t.tail(5).sum()) if not df_t.empty else 0, "f_consec": get_consecutive_days(df_f), "t_consec": get_consecutive_days(df_t), "status": "success"}
    except Exception: pass

    rev_start_date = (tw_now - datetime.timedelta(days=365*5)).strftime("%Y-%m-%d")
    rev_url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockMonthRevenue&data_id={clean_id}&start_date={rev_start_date}"
    rev_data = {"status": "fail"}
    try:
        res = requests.get(rev_url, headers=headers, timeout=5).json()
        if res.get('msg') == 'success' and len(res.get('data', [])) > 0:
            df_rev = pd.DataFrame(res['data'])
            df_rev['revenue'] = pd.to_numeric(df_rev['revenue'], errors='coerce')
            df_rev = df_rev.sort_values('date').reset_index(drop=True)
            latest_rev, latest_date = df_rev['revenue'].iloc[-1], df_rev['date'].iloc[-1]
            is_all_time_high = (latest_rev >= df_rev['revenue'].max())
            try: mom = ((latest_rev - df_rev['revenue'].iloc[-2]) / df_rev['revenue'].iloc[-2]) * 100
            except: mom = 0
            try:
                last_year_date = str(int(latest_date[:4]) - 1) + latest_date[4:]
                last_year_rev = df_rev[df_rev['date'].str.startswith(last_year_date[:7])]['revenue'].values[0]
                yoy = ((latest_rev - last_year_rev) / last_year_rev) * 100
            except: yoy = 0
            rev_data = {"latest_month": latest_date[:7], "revenue": latest_rev / 100000000, "yoy": yoy, "mom": mom, "is_high": is_all_time_high, "status": "success"}
    except Exception: pass

    return df, df_intra, tk, info, chips_data, rev_data, stock_name, quote_time, live_price, prev_close

def calculate_factors_and_score(df, chips, live_price, prev_close):
    bulls = {"籌碼與基本面": [], "價量與型態": [], "技術指標": []}
    bears = {"籌碼與基本面": [], "價量與型態": [], "技術指標": []}

    L, P = df.iloc[-1], df.iloc[-2]
    chg_pct = ((live_price - prev_close) / prev_close) * 100 if prev_close else 0

    base_c1 = live_price > L['MA21']
    base_c2 = L['Vol_Ratio'] > 1.0
    base_c3 = L['RSI'] > 50 and L['RSI'] > P['RSI']
    base_c4 = L['MACD'] > L['MACD_S']
    base_c5 = L['OBV'] > L['OBV_MA14']
    base_score = sum([base_c1, base_c2, base_c3, base_c4, base_c5])
    
    bonus1_safe = (L['MA14'] > L['MA35']) and (L['MA21'] > L['MA35'])
    bonus2_surge = (P['MA7'] <= P['MA14'] and L['MA7'] > L['MA14']) and (P['MA14'] <= P['MA21'] and L['MA14'] > L['MA21'])
    chip1_lock = chips['t_consec'] >= 3 if chips['status'] == 'success' else False
    
    total_score = base_score + (bonus1_safe * 2) + (bonus2_surge * 2) + (chip1_lock * 1)
    cond_list = [base_c1, base_c2, base_c3, base_c4, base_c5, bonus1_safe, bonus2_surge, chip1_lock]

    if chips['status'] == 'success':
        if chips['f_buy_5d'] > 0: bulls["籌碼與基本面"].append(f"外資近5日買超 {chips['f_buy_5d']:,} 張")
        elif chips['f_buy_5d'] < 0: bears["籌碼與基本面"].append(f"外資近5日賣超 {abs(chips['f_buy_5d']):,} 張")
        if chips['t_buy_5d'] > 0: bulls["籌碼與基本面"].append(f"投信近5日買超 {chips['t_buy_5d']:,} 張")
        elif chips['t_buy_5d'] < 0: bears["籌碼與基本面"].append(f"投信近5日賣超 {abs(chips['t_buy_5d']):,} 張")
        if chips['f_consec'] >= 2: bulls["籌碼與基本面"].append(f"外資連續買超 {chips['f_consec']} 天")
        elif chips['f_consec'] <= -2: bears["籌碼與基本面"].append(f"外資連續賣超 {abs(chips['f_consec'])} 天")
        if chips['t_consec'] >= 2: bulls["籌碼與基本面"].append(f"投信連續買超 {chips['t_consec']} 天")
        elif chips['t_consec'] <= -2: bears["籌碼與基本面"].append(f"投信連續賣超 {abs(chips['t_consec'])} 天")
    else:
        bulls["籌碼與基本面"].append("API 限制無法獲取籌碼")
        bears["籌碼與基本面"].append("API 限制無法獲取籌碼")
    
    if live_price >= L['Resist']: bulls["價量與型態"].append(f"強勢突破近 21 日壓力線 ({L['Resist']:.1f})")
    if live_price <= L['Support']: bears["價量與型態"].append(f"弱勢跌破近 21 日支撐線 ({L['Support']:.1f})")
    if L['MA14'] > L['MA21'] and P['MA14'] <= P['MA21']: bulls["價量與型態"].append("波段發動：MA14 上穿 MA21")
    if L['MA14'] < L['MA21'] and P['MA14'] >= P['MA21']: bears["價量與型態"].append("波段走弱：MA14 跌破 MA21")
    if bonus2_surge: bulls["價量與型態"].append("🔥 飆股共振：MA7/14/21 雙重黃金交叉")
    if bonus1_safe: bulls["價量與型態"].append("中期多頭：均線皆站穩 MA35 之上")

    vr = L['Vol_Ratio']
    if vr > 1.3: bulls["價量與型態"].append(f"今日放量突破 7 日均量 ({vr:.1f}x)")
    elif vr < 0.8: bears["價量與型態"].append(f"今日量能低迷萎縮 ({vr:.1f}x)")

    if L['OBV'] > L['OBV_MA14']: bulls["技術指標"].append("OBV 能量潮 > 14日均線 (大戶買盤強)")
    else: bears["技術指標"].append("OBV 能量潮 < 14日均線 (大戶資金流出)")
    if L['MACD_Hist'] > 0 and P['MACD_Hist'] <= 0: bulls["技術指標"].append("MACD 柱狀圖翻紅向上")
    elif L['MACD_Hist'] <= 0 and P['MACD_Hist'] > 0: bears["技術指標"].append("MACD 柱狀圖翻綠向下")
    if L['K'] > L['D']: bulls["技術指標"].append(f"KD 多頭排列 (K:{L['K']:.0f}>D:{L['D']:.0f})")
    else: bears["技術指標"].append(f"KD 空頭排列 (K:{L['K']:.0f}<D:{L['D']:.0f})")
    if L['K'] < 30: bulls["技術指標"].append("K值進入超賣區 (<30 醞釀反彈)")
    elif L['K'] > 80: bears["技術指標"].append("K值進入超買區 (>80 提防過熱)")

    return bulls, bears, chg_pct, total_score, cond_list

def generate_ai_summary(total_score, chg_pct):
    if chg_pct <= -3.0: return "<span style='color:#3fb950; font-weight:bold;'>🥶恐慌破底</span>：單日帶量長黑，動能惡化，切勿摸底接刀。"
    if chg_pct >= 4.0: return "<span style='color:#f85149; font-weight:bold;'>🚀強勢點火</span>：長紅大漲表態，短線動能極強。"
    if total_score >= 8: return "<span style='color:#f85149; font-weight:bold;'>🔥主升段啟動</span>：共振指標達成，籌碼技術皆優。"
    elif total_score >= 5: return "<span style='color:#f85149; font-weight:bold;'>📈穩健偏多</span>：基礎多方成立，沿均線防守。"
    elif total_score <= 2: return "<span style='color:#3fb950; font-weight:bold;'>🧊弱勢空頭</span>：跌破關鍵均線且大戶資金流出。"
    else: return "<span style='color:#c9d1d9; font-weight:bold;'>⚖️區間震盪</span>：多空勢均力敵，方向未明朗。"

# --- 2. 繪圖模組 ---
def draw_daily_chart(df):
    d = df.tail(80) 
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.2, 0.7])
    clrs = ['#f85149' if r['Close']>=r['Open'] else '#3fb950' for i, r in d.iterrows()]
    fig.add_trace(go.Candlestick(x=d.index, open=d['Open'], high=d['High'], low=d['Low'], close=d['Close'], increasing_line_color='#f85149', decreasing_line_color='#3fb950'), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d['MA14'], line=dict(color='#58a6ff', width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d['MA21'], line=dict(color='#d29922', width=1.5)), row=1, col=1) 
    fig.add_trace(go.Scatter(x=d.index, y=d['MA35'], line=dict(color='#8b949e', width=1.5, dash='dot')), row=1, col=1) 
    fig.add_trace(go.Bar(x=d.index, y=d['Volume'], marker_color=clrs), row=2, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d['VMA7'], line=dict(color='#8b949e', width=1.5, dash='dot')), row=2, col=1)
    fig.update_layout(margin=dict(l=0, r=0, t=5, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis_rangeslider_visible=False, showlegend=False, height=350)
    fig.update_xaxes(showgrid=True, gridcolor='#30363d'); fig.update_yaxes(showgrid=True, gridcolor='#30363d')
    return fig

def draw_intraday_chart(df_intra, prev_close):
    if df_intra is None or df_intra.empty:
        fig = go.Figure()
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', annotations=[dict(text="無盤中資料或未開盤", showarrow=False, font=dict(color="#8b949e", size=14))], height=350)
        fig.update_xaxes(showgrid=False, zeroline=False, visible=False); fig.update_yaxes(showgrid=False, zeroline=False, visible=False)
        return fig
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_width=[0.2, 0.7])
    last_price = df_intra['Close'].iloc[-1]
    line_color = '#f85149' if last_price >= prev_close else '#3fb950'
    fig.add_trace(go.Scatter(x=df_intra.index, y=df_intra['Close'], mode='lines', line=dict(color=line_color, width=2)), row=1, col=1)
    fig.add_hline(y=prev_close, line_dash="dash", line_color="#8b949e", line_width=1, row=1, col=1)
    clrs = ['#f85149' if r['Close']>=r['Open'] else '#3fb950' for i, r in df_intra.iterrows()]
    fig.add_trace(go.Bar(x=df_intra.index, y=df_intra['Volume'], marker_color=clrs), row=2, col=1)
    y_max, y_min = max(df_intra['High'].max(), prev_close), min(df_intra['Low'].min(), prev_close)
    y_padding = (y_max - y_min) * 0.15 
    if y_padding == 0: y_padding = prev_close * 0.01 
    fig.update_layout(margin=dict(l=0, r=0, t=5, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis_rangeslider_visible=False, showlegend=False, height=350)
    fig.update_xaxes(tickformat="%H:%M", showgrid=True, gridcolor='#30363d')
    fig.update_yaxes(range=[y_min - y_padding, y_max + y_padding], showgrid=True, gridcolor='#30363d', row=1, col=1)
    fig.update_yaxes(showgrid=True, gridcolor='#30363d', row=2, col=1)
    return fig

# --- 🚀 超薄頂部導覽列 ---
col_logo, col_input, col_btn, col_hist = st.columns([1, 1, 0.5, 6], gap="small")
with col_logo: st.markdown("<div style='color:#58a6ff; font-weight:900; font-size:15px; margin-top:8px;'>⚡ 股票決策終端</div>", unsafe_allow_html=True)
with col_input: st.text_input("代碼", value=st.session_state['target'], key="search_input", label_visibility="collapsed")
with col_btn:
    if st.button("分析", type="primary", use_container_width=True): st.session_state['target'] = st.session_state['search_input'].strip()
with col_hist:
    h_cols = st.columns(len(st.session_state['history'][:10]))
    for i, (c, n) in enumerate(st.session_state['history'][:10]):
        with h_cols[i]:
            if st.button(f"{c} {n[:4]}", key=f"h_{c}", type="secondary", use_container_width=True):
                st.session_state['target'] = c; st.rerun()

st.markdown("<hr style='margin: 5px 0 10px 0; border-color: #30363d;'>", unsafe_allow_html=True)

# --- 主體執行區塊 ---
tc = st.session_state['target']

with st.spinner(f"分析 ({tc}) 中..."):
    df, df_intra, _, info, chips, rev, stock_name, quote_time, live_price, prev_close = get_data(tc)
    
    if df is not None:
        new_hist = [(code, name) for code, name in st.session_state['history'] if code != tc]
        new_hist.insert(0, (tc, stock_name))
        st.session_state['history'] = new_hist[:10]
        
        L = df.iloc[-1]
        bulls, bears, chg_pct, total_score, cond_list = calculate_factors_and_score(df, chips, live_price, prev_close)
        chg = live_price - prev_close
        ai_summary = generate_ai_summary(total_score, chg_pct)
        
        clr = "text-red" if chg > 0 else "text-green" if chg < 0 else "text-white"
        sgn = "+" if chg > 0 else ""
        
        bull_count, bear_count = sum([len(v) for v in bulls.values()]), sum([len(v) for v in bears.values()])
        total_c = bull_count + bear_count
        bull_pct = (bull_count / total_c * 100) if total_c > 0 else 50
        bear_pct = (bear_count / total_c * 100) if total_c > 0 else 50
        t_color = "#f85149" if bull_count > bear_count else "#3fb950" if bear_count > bull_count else "#c9d1d9"
        
        def g_list(items, bg): return "".join([f"<div style='padding:4px 8px; margin-bottom:2px; background:{bg}; color:#c9d1d9; font-size:12px; border-radius:3px;'>{item}</div>" for item in items]) if items else "<div style='font-size:12px; color:#6e7681; padding:4px;'>-</div>"
        def g_block(cat): return f"<div style='color:#8b949e; font-size:11px; margin:8px 0 2px 0;'>{cat}</div><div style='display:flex; gap:4px;'><div style='flex:1;'>{g_list(bulls[cat], 'rgba(248,81,73,0.15)')}</div><div style='flex:1;'>{g_list(bears[cat], 'rgba(63,185,80,0.15)')}</div></div>"

        def check_item(is_pass, title, desc):
            icon = "<span class='text-red'>✅</span>" if is_pass else "<span class='text-green'>❌</span>"
            return f"<details style='margin-bottom:2px;'><summary>{icon} <span class='dotted-link'>{title}</span></summary><div class='info-box'>{desc}</div></details>"

        st.markdown(f"""
        <div class="d-card" style="padding:10px 15px; margin-bottom:10px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
            <div style="display:flex; align-items:baseline; gap:12px; flex-wrap:wrap;">
                <div style="color:#fff; font-size:20px; font-weight:900;">{stock_name} ({tc})</div>
                <div style="font-size:28px; font-weight:900;" class="{clr}">{live_price:.2f}</div>
                <div style="font-size:16px; font-weight:bold;" class="{clr}">{sgn}{chg:.2f} ({sgn}{chg_pct:.2f}%)</div>
                <div style="font-size:11px; color:#8b949e;">🕒 {quote_time}</div>
            </div>
            <div style="background:rgba(88,166,255,0.1); border-left:3px solid #58a6ff; padding:6px 12px; border-radius:4px; color:#c9d1d9; font-size:13px; max-width:500px;">
                {ai_summary}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col_main, col_side = st.columns([1.5, 1], gap="medium")
        
        with col_main:
            tab1, tab2 = st.tabs(["📉 盤中走勢", "📊 技術 K 線"])
            with tab1:
                st.markdown('<div class="d-card" style="padding:0; margin-bottom:10px;">', unsafe_allow_html=True)
                st.plotly_chart(draw_intraday_chart(df_intra, prev_close), use_container_width=True, config={'displayModeBar':False})
                st.markdown('</div>', unsafe_allow_html=True)
            with tab2:
                st.markdown('<div class="d-card" style="padding:0; margin-bottom:10px;">', unsafe_allow_html=True)
                st.plotly_chart(draw_daily_chart(df), use_container_width=True, config={'displayModeBar':False})
                st.markdown('</div>', unsafe_allow_html=True)
                
            high_bdg = "<span style='color:#f85149; font-size:9px; border:1px solid #f85149; padding:1px 2px; border-radius:2px; margin-left:4px;'>新高</span>" if rev['status']=='success' and rev['is_high'] else ""
            rev_val = f"{rev['revenue']:.1f}億{high_bdg}" if rev['status']=='success' else "無資料"
            yoy_val = f"<span class='{'text-red' if rev['yoy']>0 else 'text-green'}'>{rev['yoy']:.1f}%</span>" if rev['status']=='success' else "-"

            st.markdown(f"""
            <div class="g-4">
                <div class="m-box"><div class="m-title">本月營收</div><div class="m-val" style="font-size:15px;">{rev_val}</div><div style="font-size:10px; color:#8b949e;">YoY {yoy_val}</div></div>
                <div class="m-box"><div class="m-title">法人共識</div><div class="m-val text-white" style="font-size:15px; text-transform:capitalize;">{info.get('recommendationKey','N/A').replace('_',' ')}</div></div>
                <div class="m-box"><div class="m-title">本益比</div><div class="m-val text-white" style="font-size:15px;">{safe_float(info.get('trailingPE'))}</div><div style="font-size:10px; color:#8b949e;">預估 {safe_float(info.get('forwardPE'))}</div></div>
                <div class="m-box"><div class="m-title">殖利率</div><div class="m-val text-white" style="font-size:15px;">{safe_float(info.get('dividendYield'), True)}</div></div>
            </div>
            """, unsafe_allow_html=True)

        with col_side:
            st.markdown(f"""
            <div class="d-card" style="padding:12px; margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <div style="font-size:18px; font-weight:900; color:{t_color};">多空對決</div>
                    <div style="font-size:16px; font-weight:bold; background:#21262d; padding:2px 8px; border-radius:4px;" class="{'text-red' if total_score>=7 else 'text-green' if total_score<=3 else 'text-yellow'}">評分 {total_score}/10</div>
                </div>
                <div style="width:100%; height:4px; display:flex; border-radius:2px; overflow:hidden; margin-bottom:6px; background:#21262d;">
                    <div style="width:{bull_pct}%; background-color:#f85149;"></div><div style="width:{bear_pct}%; background-color:#3fb950;"></div>
                </div>
                <div style="display:flex; border-bottom:1px solid #30363d; padding-bottom:4px; font-size:11px; font-weight:bold;">
                    <div style="flex:1; text-align:center; color:#f85149;">多方 ({bull_count})</div><div style="flex:1; text-align:center; color:#3fb950;">空方 ({bear_count})</div>
                </div>
                {g_block("籌碼與基本面")}
                {g_block("價量與型態")}
                {g_block("技術指標")}
            </div>
            
            <div class="d-card" style="padding:10px; padding-bottom:4px;">
                <div style="color:#fff; font-size:13px; font-weight:900; border-bottom:1px solid #30363d; padding-bottom:4px; margin-bottom:4px;">🏆 波段檢核清單 (點擊說明)</div>
                <div style="color:#8b949e; font-size:10px; margin-top:2px; font-weight:bold;">基礎五要件 (滿分5分)</div>
                {check_item(cond_list[0], f"站上 MA21 波段線", "股價站上月均線，趨勢由弱轉強。")}
                {check_item(cond_list[1], "量能充足 (> 7日均量)", "成交量大於平均，推升具備延續性。")}
                {check_item(cond_list[2], "RSI 強勢向上 (> 50)", "多方力道勝過空方，且持續上升。")}
                {check_item(cond_list[3], "MACD 處於多方區間", "快線大於慢線，中期趨勢多頭。")}
                {check_item(cond_list[4], "OBV 能量潮 > 14日線", "大戶與主力真實資金正在吃貨。")}
                <div style="color:#8b949e; font-size:10px; margin-top:4px; font-weight:bold;">核心加分項 (滿分4分)</div>
                {check_item(cond_list[5], "中期多頭保護：均線站穩 MA35", "短線均線皆站上中期均線，過濾跌深反彈股。")}
                {check_item(cond_list[6], "飆股共振：短中線雙重金叉", "多個週期均線同時向上發散，極強勢發動特徵。")}
                <div style="color:#8b949e; font-size:10px; margin-top:4px; font-weight:bold;">籌碼加分項 (滿分1分)</div>
                {check_item(cond_list[7], "法人鎖碼：投信連買 >= 3 天", "投信波段集中作帳，形成強大推升力道。")}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.error(f"⚠️ 找不到股票代碼 **{tc}** 的資料，或伺服器暫時忙碌中。")
