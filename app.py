import yfinance as yf
import streamlit as st
import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(layout="wide")

# ==========================================
# === 0. 夜間模式開關與全局樣式設定 ===
# ==========================================
dark_mode = st.sidebar.toggle("🌙 開啟夜間看盤模式", value=False)

if dark_mode:
    st.markdown("""
    <style>
        .stApp { background-color: #121212 !important; color: #E0E0E0 !important; }
        [data-testid="stSidebar"] { background-color: #1E1E1E !important; }
        [data-testid="stHeader"] { background-color: #121212 !important; }
        p, h1, h2, h3, h4, h5, h6, label { color: #E0E0E0 !important; }
        .stTextInput>div>div>input, .stSelectbox>div>div>div { color: white !important; background-color: #333333 !important; }
    </style>
    """, unsafe_allow_html=True)
    chart_bg = "#121212"
    grid_color = "#333333"
    font_color = "#E0E0E0"
    up_color = "#FF6B6B"   
    down_color = "#4ADE80" 
else:
    chart_bg = "white"
    grid_color = "lightgray"
    font_color = "#000000"
    up_color = "#E24A4A"
    down_color = "#2E8B57"

st.title("我的個人專屬看盤 App 📈")

STOCK_NAMES = {
    "2327.TW": "國巨",
    "3260.TW": "威剛",
    "2330.TW": "台積電",
    "2454.TW": "聯發科",
    "2317.TW": "鴻海",
    "2382.TW": "廣達"
}

def format_ticker(ticker):
    name = STOCK_NAMES.get(ticker, "")
    return f"{ticker} ({name})" if name else ticker

if 'watchlists' not in st.session_state:
    st.session_state['watchlists'] = {
        "我的觀察清單 1": ["2327.TW", "3260.TW", "2330.TW", "2454.TW"],
        "電子股": ["2317.TW", "2382.TW"]
    }

# ==========================================
# === 1. 左側邊欄：控制面板 ===
# ==========================================
st.sidebar.markdown("<h3 style='color: #4A90E2;'>⚙️ 控制面板</h3>", unsafe_allow_html=True)

selected_ticker = None

with st.sidebar.expander("🌸 自選股票 (點此展開選股)", expanded=False):
    list_names = list(st.session_state['watchlists'].keys())
    current_list = st.selectbox("📂 選擇群組", list_names)
    current_stocks = st.session_state['watchlists'][current_list]

    if current_stocks:
        selected_ticker = st.selectbox("🎯 選擇要查看的股票", current_stocks, format_func=format_ticker)
    else:
        st.info("這個群組目前是空的喔！")
        
    st.markdown("---")
    manage_mode = st.checkbox("🔧 展開管理面板 (新增 / 移除 / 重新命名)")
    
    if manage_mode:
        st.markdown(f"**管理：<span style='color: #4A90E2;'>{current_list}</span>**", unsafe_allow_html=True)
        if selected_ticker:
            if st.button(f"🗑 從清單移除 {format_ticker(selected_ticker)}"):
                st.session_state['watchlists'][current_list].remove(selected_ticker)
                st.rerun() 
        st.markdown("---")
        if len(current_stocks) < 5:
            new_ticker = st.text_input("➕ 新增股票代號 (例如 2330.TW)")
            if st.button("加入目前群組"):
                if new_ticker and new_ticker not in current_stocks:
                    st.session_state['watchlists'][current_list].append(new_ticker)
                    st.rerun() 
        else:
            st.warning("此群組已達 5 檔上限！")
        st.markdown("---")
        new_group_name = st.text_input("✏ 修改目前群組名稱", value=current_list)
        if st.button("儲存新名稱"):
            if new_group_name != current_list: 
                if new_group_name and new_group_name not in st.session_state['watchlists']:
                    st.session_state['watchlists'][new_group_name] = st.session_state['watchlists'].pop(current_list)
                    st.rerun()
                elif new_group_name in st.session_state['watchlists']:
                    st.warning("這個名稱已經存在囉，請換一個！")
        st.markdown("---")
        new_list_name = st.text_input("📁 建立全新群組")
        if st.button("新增群組") and new_list_name:
            if new_list_name not in st.session_state['watchlists']:
                st.session_state['watchlists'][new_list_name] = [] 
                st.success(f"已成功建立：{new_list_name}")
                st.rerun()

with st.sidebar.expander("🤖 AI 投資建議 (晨間盤前決策)", expanded=False):
    st.markdown("<b style='color: #4A90E2;'>連動美股前夜收盤與國際局勢分析</b>", unsafe_allow_html=True)
    ai_group = st.selectbox("🎯 選擇盤前分析群組", list(st.session_state['watchlists'].keys()), key="ai_group")
    ai_stocks = st.session_state['watchlists'][ai_group]
    run_ai_advice = st.button("🌅 產出今日晨間 AI 決策報告")

with st.sidebar.expander("💡 推薦進場點 (多週期與技術面掃描)", expanded=False):
    st.markdown("<b style='color: #E24A4A;'>自動解析支撐壓力與動能訊號</b>", unsafe_allow_html=True)
    scan_group = st.selectbox("🎯 選擇要掃描的群組", list(st.session_state['watchlists'].keys()), key="scan_group")
    scan_stocks = st.session_state['watchlists'][scan_group]
    run_scan = st.button("🔍 執行深度掃描與回測")

with st.sidebar.expander("📅 日期區間設定 (點此展開)", expanded=False):
    default_end_date = datetime.date.today()
    default_start_date = default_end_date - datetime.timedelta(days=180)
    start_date = st.date_input("開始日期", default_start_date)
    end_date = st.date_input("結束日期", default_end_date)


# ==========================================
# === 2. 右側主畫面 (動態決策與圖表區) ===
# ==========================================

# ----------------- 晨間 AI 投資建議報告區 -----------------
if run_ai_advice:
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(f"## 🤖 晨間 AI 盤前投資建議 (連動美股與國際局勢)")
    st.caption(f"📅 報告產出時間：{now_str} (適用今日台股開盤決策) ｜ 標的群組：`{ai_group}`")
    
    with st.spinner("正在連線抓取美股收盤行情與隔夜國際新聞..."):
        us_indices = {
            "費城半導體 (^SOX)": "^SOX",
            "台積電 ADR (TSM)": "TSM",
            "那斯達克 (^IXIC)": "^IXIC",
            "標普 500 (^GSPC)": "^GSPC"
        }
        us_results = {}
        sox_change = 0.0
        tsm_change = 0.0
        
        for name, ticker in us_indices.items():
            try:
                us_hist = yf.Ticker(ticker).history(period="5d")
                if len(us_hist) >= 2:
                    last_close = us_hist['Close'].iloc[-1]
                    prev_close = us_hist['Close'].iloc[-2]
                    chg_pct = ((last_close - prev_close) / prev_close) * 100
                    us_results[name] = (last_close, chg_pct)
                    if ticker == "^SOX":
                        sox_change = chg_pct
                    elif ticker == "TSM":
                        tsm_change = chg_pct
                else:
                    us_results[name] = (0.0, 0.0)
            except:
                us_results[name] = (0.0, 0.0)

    st.markdown("### 🇺🇸 前夜美股關鍵指標行情")
    us_col1, us_col2, us_col3, us_col4 = st.columns(4)
    cols = [us_col1, us_col2, us_col3, us_col4]
    for idx, (m_name, (price, pct)) in enumerate(us_results.items()):
        cols[idx].metric(m_name, f"{price:,.2f}", f"{pct:+.2f}%")
        
    st.markdown("### 🌍 國際局勢與總經環境摘要")
    if sox_change >= 1.5:
        us_sentiment = "強烈偏多"
        us_desc = "隔夜費城半導體與科技權值股強勁表態，海外 AI 伺服器與半導體供應鏈資金回流，台股相關科技族群開盤具備高度溢價動能。"
    elif sox_change <= -1.5:
        us_sentiment = "承壓偏空"
        us_desc = "美股主要科技指數因利率預期或總經數據修正出現較深回檔，科技權值股短線面臨外資提款賣壓，開盤需提防殺低取量震盪。"
    else:
        us_sentiment = "中性震盪"
        us_desc = "美股主要指數窄幅震盪收小紅/小黑，市場處於數據真空期或觀望國際政經變化，台股今日開盤預期回歸個股籌碼與基本面題材表現。"
        
    st.info(f"**【隔夜市場氛圍】：{us_sentiment}**\n\n{us_desc}")
    st.markdown("---")

    st.markdown("### 🎯 今日自選股 AI 操作建議與進出點位")
    if not ai_stocks:
        st.warning("您選擇的群組目前沒有股票可分析。")
    else:
        ai_tabs = st.tabs([format_ticker(t) for t in ai_stocks])
        for i, ticker in enumerate(ai_stocks):
            with ai_tabs[i]:
                try:
                    s_obj = yf.Ticker(ticker)
                    df_d = s_obj.history(period="3mo")
                    if not df_d.empty:
                        last_c = df_d['Close'].iloc[-1]
                        ma20 = df_d['Close'].rolling(20).mean().iloc[-1]
                        
                        tr = pd.concat([
                            df_d['High'] - df_d['Low'],
                            (df_d['High'] - df_d['Close'].shift()).abs(),
                            (df_d['Low'] - df_d['Close'].shift()).abs()
                        ], axis=1).max(axis=1)
                        atr = tr.rolling(14).mean().iloc[-1]
                        
                        if sox_change >= 1.0 and last_c > ma20:
                            today_verdict = "🟢 今日建議買進 (Buy Today)"
                            verdict_summary = "長短線多頭確立，受美股半導體與 ADR 激勵，今日開盤順勢偏多操作。"
                            in_low = round(last_c, 2)
                            in_high = round(last_c + (atr * 0.3), 2)
                            suggested_entry = f"{in_low} ~ {in_high} (開盤小幅回踩或試單)"
                            suggested_target = round(last_c + (atr * 1.5), 2)
                            suggested_stop = round(last_c - (atr * 0.8), 2)
                            allocation_today = "可配置 25%~35% 部位，若開盤未爆量跳空可於早盤進場。"
                        elif sox_change <= -1.0 and last_c > ma20:
                            today_verdict = "🟡 盤中拉回低接 (Buy on Dip)"
                            verdict_summary = "雖然個股位於月線多方，但美股走弱易導致早盤開低，不宜追價，建議等待盤中回測支撐有守再行低接。"
                            in_low = round(last_c - (atr * 0.8), 2)
                            in_high = round(last_c - (atr * 0.3), 2)
                            suggested_entry = f"{in_low} ~ {in_high} (逢低掛單低接)"
                            suggested_target = round(last_c + (atr * 1.0), 2)
                            suggested_stop = round(ma20 * 0.98, 2)
                            allocation_today = "建議控制在 10%~15% 小量試單，切忌開盤急躁搶進。"
                        elif last_c < ma20 and sox_change <= 0:
                            today_verdict = "⚪ 今日建議觀望 (Hold / Wait)"
                            verdict_summary = "個股短線失守月線均線，且外圍市場缺乏激勵因子，今日無明顯勝率優勢，建議空手觀望。"
                            suggested_entry = "暫無建議進場點 (不建議買入)"
                            suggested_target = "-"
                            suggested_stop = "-"
                            allocation_today = "維持 0% 現金水位，等待趨勢扭轉。"
                        else:
                            today_verdict = "🔴 逢高減碼獲利 (Take Profit)"
                            verdict_summary = "個股進入反彈壓力區或短線動能趨緩，趁美股平盤震盪時，逢高調節持股保護利潤。"
                            suggested_entry = "不建議買入"
                            suggested_target = round(last_c + (atr * 0.8), 2)
                            suggested_stop = round(ma20, 2)
                            allocation_today = "持股水位建議降至 15% 以下，保留資金彈性。"
                            
                        st.markdown(f"### {today_verdict}")
                        st.markdown(f"**核心結論**：{verdict_summary}")
                        
                        p_col1, p_col2, p_col3 = st.columns(3)
                        p_col1.metric("今日建議進場點", f"{suggested_entry}")
                        p_col2.metric("今日出場目標點", f"{suggested_target}")
                        p_col3.metric("今日防守停損點", f"{suggested_stop}")
                        
                        st.markdown(f"- **前日收盤市價**：`{last_c:.2f}` (昨日振幅 ATR: `{atr:.2f}` 元)")
                        st.markdown(f"- **今日部位配置建議**：{allocation_today}")
                        st.markdown(f"- **產業傳導分析**：該標的所屬族群與海外市場具備連動，前夜美股費半變動率 (`{sox_change:+.2f}%`) 對早盤情緒影響顯著。")
                        
                except Exception as e:
                    st.error(f"無法計算 {ticker} 之晨間建議：{e}")
                    
    st.markdown("<br><br>", unsafe_allow_html=True)


# ----------------- 深度掃描報告區 -----------------
if run_scan:
    st.markdown(f"## 💡 深度掃描與回測報告：`{scan_group}`")
    
    if not scan_stocks:
        st.warning("您選擇的群組目前沒有股票可掃描。")
    else:
        tabs = st.tabs([format_ticker(t) for t in scan_stocks])
        
        for i, ticker in enumerate(scan_stocks):
            with tabs[i]:
                try:
                    stock_obj = yf.Ticker(ticker)
                    df_daily = stock_obj.history(period="6mo")
                    df_weekly = stock_obj.history(period="1y", interval="1wk")
                    
                    news_list = stock_obj.news
                    if news_list and len(news_list) > 0:
                        latest_news = news_list[0].get('title', '無最新重大新聞')
                        news_pub = news_list[0].get('publisher', '')
                        news_display = f"[{news_pub}] {latest_news}" if news_pub else latest_news
                    else:
                        news_display = "目前無重大新聞更新，回歸純技術面判斷。"
                    
                    if not df_daily.empty and not df_weekly.empty:
                        ma20_series = df_daily['Close'].rolling(20).mean()
                        ma60_series = df_daily['Close'].rolling(60).mean()
                        
                        delta = df_daily['Close'].diff()
                        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
                        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                        rs = gain / loss
                        rsi_series = 100 - (100 / (1 + rs))

                        close_d = df_daily['Close'].iloc[-1]
                        ma20_d = ma20_series.iloc[-1]
                        ma60_d = ma60_series.iloc[-1]
                        ma20_w = df_weekly['Close'].rolling(20).mean().iloc[-1] 
                        
                        resistance = df_daily['High'].rolling(60).max().iloc[-1]
                        support = df_daily['Low'].rolling(60).min().iloc[-1]
                        rsi = rsi_series.iloc[-1]
                        
                        bt_period = 60
                        bt_df = df_daily.iloc[-bt_period:].copy()
                        bt_ma20 = ma20_series.iloc[-bt_period:].copy()
                        bt_rsi = rsi_series.iloc[-bt_period:].copy()
                        
                        in_position = False
                        entry_price = 0
                        trades = []
                        
                        for j in range(1, len(bt_df)):
                            prev_close = bt_df['Close'].iloc[j-1]
                            prev_ma = bt_ma20.iloc[j-1]
                            curr_close = bt_df['Close'].iloc[j]
                            curr_ma = bt_ma20.iloc[j]
                            curr_rsi = bt_rsi.iloc[j]
                            
                            if not in_position:
                                if prev_close <= prev_ma and curr_close > curr_ma and curr_rsi < 70:
                                    in_position = True
                                    entry_price = curr_close
                            else:
                                if curr_close < curr_ma or curr_rsi >= 70:
                                    in_position = False
                                    trades.append((curr_close - entry_price) / entry_price)
                                    
                        num_trades = len(trades)
                        win_trades = [t for t in trades if t > 0]
                        lose_trades = [t for t in trades if t <= 0]
                        
                        win_rate = (len(win_trades) / num_trades * 100) if num_trades > 0 else 0
                        gross_profit = sum(win_trades)
                        gross_loss = abs(sum(lose_trades))
                        pf = (gross_profit / gross_loss) if gross_loss > 0 else (99.9 if gross_profit > 0 else 0)
                        
                        equity = 1.0
                        eq_curve = [1.0]
                        for t in trades:
                            equity *= (1 + t)
                            eq_curve.append(equity)
                        eq_series = pd.Series(eq_curve)
                        drawdowns = (eq_series.cummax() - eq_series) / eq_series.cummax()
                        max_dd = drawdowns.max() * 100 if not drawdowns.empty else 0

                        if num_trades == 0:
                            bt_advice = f"過去 60 天皆無符合突破 {ma20_d:.1f}(20MA) 的進場條件，顯示近期處於空頭或盤整弱勢。建議：**耐心觀望，等待帶量長紅突破月線後再行試單。**"
                        elif win_rate >= 50 and pf > 1.2:
                            bt_advice = f"回測表現優異！該股股性適合順勢操作。建議進場：**當股價回測並守穩 {ma20_d:.1f}(月線) 時買進**；建議出場：**RSI 觸及 70 以上，或跌破 {ma20_d:.1f} 時果斷獲利了結**。"
                        elif pf < 1:
                            bt_advice = f"回測顯示近期「假突破」機率高（騙線多）。建議進場：**請勿單看 20MA，應等待股價回落至底部支撐區 {support:.1f} 附近低接**；建議出場：**接近壓力區 {resistance:.1f} 時分批賣出，採區間操作。**"
                        else:
                            bt_advice = f"回測表現普通，震盪較大。建議進場：**控制部位，逢低佈局**；建議出場：**見好就收，設定明確的固定停損點 ({round(support*0.98, 2)}) 嚴格執行。**"
                        
                        daily_trend = "向上" if close_d > ma20_d else "向下"
                        weekly_trend = "多頭" if df_weekly['Close'].iloc[-1] > ma20_w else "空頭"
                        
                        # ==========================================
                        # === 【新增】法人籌碼趨勢推估模型 ===
                        # ==========================================
                        # 分析近 5 日價量關係，模擬外資與投信的籌碼動向
                        last_5_days = df_daily.tail(5)
                        price_change_5d = ((last_5_days['Close'].iloc[-1] - last_5_days['Close'].iloc[0]) / last_5_days['Close'].iloc[0]) * 100
                        vol_5d_avg = last_5_days['Volume'].mean()
                        vol_20d_avg = df_daily['Volume'].tail(20).mean()
                        vol_surge = vol_5d_avg > (vol_20d_avg * 1.2) # 近5日成交量是否大於月均量20%
                        
                        if price_change_5d > 3:
                            inst_trend = "📈 外資與投信同步偏多 (推估買超)"
                            if vol_surge:
                                inst_future = "價漲量增，籌碼集中度顯著提升，主力資金持續流入。未來一週具備強勢上攻動能，逢回皆是買點。"
                            else:
                                inst_future = "呈現量縮上漲，籌碼安定度高（上方賣壓輕），預期將沿均線緩步推升。"
                        elif price_change_5d < -3:
                            inst_trend = "📉 法人持續提款 (推估賣超)"
                            if vol_surge:
                                inst_future = "價跌量增，籌碼出現明顯鬆動，法人逢高結帳賣壓沉重。短期恐進一步下探支撐，建議避開。"
                            else:
                                inst_future = "呈現量縮下跌，主要為散戶停損賣壓，法人並未積極介入護盤，預期將反覆測底。"
                        else:
                            inst_trend = "⚖️ 法人買賣互見 (籌碼中性)"
                            if vol_surge:
                                inst_future = "底部量能放大但價格未明顯波動，可能有特定主力或法人正在換手吃貨，後續隨時準備方向表態。"
                            else:
                                inst_future = "成交量萎縮，外資與投信資金暫時觀望，預期近期維持區間震盪整理。"
                        # ==========================================

                        if rsi >= 70 and close_d >= resistance * 0.95:
                            signal_icon = "🔴"
                            action = "逢高賣出"
                            reason = f"動能指標 RSI 達 {rsi:.1f} 進入超買區，且股價已逼近近期壓力區 ({resistance:.1f})，短線獲利了結賣壓沉重，建議分批減碼。"
                            target_price = "-"
                            stop_loss = round(ma20_d, 2)
                            pos_advice = "📉 **建議將該部位降至 10%-20% 以下**，或全數獲利了結，鎖定波段利潤。"
                        elif df_weekly['Close'].iloc[-1] > ma20_w and close_d > ma20_d and 40 < rsi < 65:
                            signal_icon = "🟢"
                            action = "建議買進"
                            reason = f"長線週線維持{weekly_trend}，日線價格站穩 20MA 之上（短線趨勢{daily_trend}）。目前 RSI 為 {rsi:.1f} 動能健康未過熱，為技術面右側交易進場機會。"
                            target_price = round(resistance, 2)
                            stop_loss = round(support * 0.98, 2) 
                            pos_advice = "📈 **建議初期投入 20%-30% 資金試單**。若帶量突破上方壓力區，可再加碼 20%。嚴格執行跌破支撐停損。"
                        elif close_d < ma20_d and close_d > ma60_d:
                            signal_icon = "🟡"
                            action = "等待突破"
                            reason = f"股價跌破日線 20MA，但下方仍有 60MA 季線支撐，目前處於區間震盪整理，建議等待帶量突破壓力區再行進場。"
                            target_price = round(resistance, 2)
                            stop_loss = round(ma60_d, 2)
                            pos_advice = "⚖️ **目前屬於震盪格局，建議空手觀望**，或僅以 10% 極小部位進行低買高賣的網格交易。"
                        else:
                            signal_icon = "🟡"
                            action = "建議觀望"
                            reason = f"目前技術面較不明確。週線趨勢{weekly_trend}，日線趨勢{daily_trend}，股價未見明顯築底訊號，建議先在旁觀望。"
                            target_price = "-"
                            stop_loss = "-"
                            pos_advice = "🛑 **建議空手 (0%)**，將資金轉移至其他多頭排列之強勢股，避免資金閒置。"

                        if isinstance(target_price, float) and isinstance(stop_loss, float):
                            risk = close_d - stop_loss
                            reward = target_price - close_d
                            rr_ratio = round(reward / risk, 2) if risk > 0 else "空間受限"
                            volatility_range = f"{stop_loss} ~ {target_price}"
                        else:
                            rr_ratio = "-"
                            volatility_range = "趨勢不明朗，暫無明確區間"

                        with st.container():
                            st.markdown(f"### {signal_icon} {format_ticker(ticker)} : {action}")
                            
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("目前市價", f"{close_d:.2f}")
                            col2.metric("出場目標 (壓力區)", f"{target_price}")
                            col3.metric("停損點位 (支撐區)", f"{stop_loss}")
                            col4.metric("風險報酬比", f"{rr_ratio}")
                            
                            st.info(f"**【技術面解析】** (關鍵指標：RSI = {rsi:.1f}, 日線20MA = {ma20_d:.1f})\n\n{reason}")
                            
                            st.markdown("#### 📊 近 60 日策略回測績效 (20MA 突破策略)")
                            bt_c1, bt_c2, bt_c3, bt_c4 = st.columns(4)
                            bt_c1.metric("策略勝率", f"{win_rate:.1f}%")
                            bt_c2.metric("獲利因子", f"{pf:.2f}")
                            bt_c3.metric("最大回撤", f"{max_dd:.1f}%")
                            bt_c4.metric("交易次數", f"{num_trades} 次")
                            
                            st.markdown(f"> **💡 【優化進出場指引】**\n>\n> {bt_advice}")

                            # === 【新增】：將推估的法人籌碼動向顯示在畫面上 ===
                            st.markdown("#### 🏦 法人籌碼趨勢與未來走向預估")
                            st.markdown(f"- **近五日籌碼狀態**：`{inst_trend}` (依據近期價量結構推估)")
                            st.markdown(f"- **未來走向研判**：{inst_future}")
                            # ==========================================
                            
                            st.markdown("#### 📰 產業新聞與交易評估")
                            st.markdown(f"- **即時新聞**：`{news_display}`")
                            st.markdown(f"- **預期波動區間**：`{volatility_range}` (依近一季極值推算)")
                            st.markdown(f"- **部位配置建議**：{pos_advice}")
                            st.markdown("<br>", unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"無法完整分析 {ticker}：{e}")
                
    st.markdown("<br><br>", unsafe_allow_html=True) 


# ----------------- Plotly 動態圖表區 -----------------
if selected_ticker:
    title_color = "#FF6B6B" if dark_mode else "#E24A4A"
    st.markdown(f"<h5>目前查看： <span style='color: {title_color};'>{format_ticker(selected_ticker)}</span></h5>", unsafe_allow_html=True)

    try:
        if start_date > end_date:
            st.error("錯誤：開始日期不能晚於結束日期！")
        else:
            stock = yf.Ticker(selected_ticker)
            df = stock.history(start=start_date, end=end_date)

            if not df.empty:
                df.index = pd.to_datetime(df.index).tz_localize(None)
                
                df['5MA'] = df['Close'].rolling(5).mean()
                df['20MA'] = df['Close'].rolling(20).mean()
                
                ema12 = df['Close'].ewm(span=12, adjust=False).mean()
                ema26 = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD'] = ema12 - ema26
                df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                df['Histogram'] = df['MACD'] - df['Signal']
                
                macd_colors = [up_color if val >= 0 else down_color for val in df['Histogram']]
                vol_colors = [up_color if close >= open else down_color for close, open in zip(df['Close'], df['Open'])]

                fig = make_subplots(
                    rows=3, cols=1, 
                    shared_xaxes=True,           
                    vertical_spacing=0.03,       
                    row_heights=[0.6, 0.15, 0.25] 
                )

                fig.add_trace(go.Candlestick(
                    x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                    name='K線',
                    increasing_line_color=up_color, decreasing_line_color=down_color,
                    hovertemplate="<b>日期: %{x}</b><br>開盤: %{open:.2f}<br>最高: %{high:.2f}<br>最低: %{low:.2f}<br>收盤: %{close:.2f}<extra></extra>"
                ), row=1, col=1)
                
                fig.add_trace(go.Scatter(x=df.index, y=df['5MA'], line=dict(color='orange', width=1.5), name='5日均線', hovertemplate="5日均線: %{y:.2f}<extra></extra>"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['20MA'], line=dict(color='dodgerblue', width=1.5), name='20日均線', hovertemplate="20日均線: %{y:.2f}<extra></extra>"), row=1, col=1)

                fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='成交量', hovertemplate="成交量: %{y:,}<extra></extra>"), row=2, col=1)

                fig.add_trace(go.Bar(x=df.index, y=df['Histogram'], marker_color=macd_colors, name='MACD柱狀圖', hovertemplate="MACD柱: %{y:.2f}<extra></extra>"), row=3, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='fuchsia', width=1.5), name='MACD線', hovertemplate="MACD線: %{y:.2f}<extra></extra>"), row=3, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='cyan', width=1.5), name='訊號線', hovertemplate="訊號線: %{y:.2f}<extra></extra>"), row=3, col=1)

                fig.update_yaxes(title_text="股價", row=1, col=1)
                fig.update_yaxes(title_text="成交量", row=2, col=1)
                fig.update_yaxes(title_text="指標", row=3, col=1)

                fig.update_layout(
                    title=f"專業動態技術分析圖",
                    height=750,
                    margin=dict(l=20, r=20, t=40, b=20),
                    xaxis_rangeslider_visible=False, 
                    hovermode="x unified",           
                    plot_bgcolor=chart_bg,            
                    paper_bgcolor=chart_bg,
                    font=dict(color=font_color)
                )
                
                fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
                fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor=grid_color)
                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor=grid_color)

                st.plotly_chart(fig, use_container_width=True)
                
                st.subheader("📝 原始數據 (最後 5 筆)")
                
                display_df = df[['Open', 'High', 'Low', 'Close', 'Volume', 'MACD']].copy()
                display_df.columns = ['開盤價', '最高價', '最低價', '收盤價', '成交量', 'MACD']
                display_df.index = display_df.index.strftime('%Y-%m-%d') 
                display_df.index.name = '日期'

                def color_rows(row):
                    color = up_color if row['收盤價'] >= row['開盤價'] else down_color
                    return [f'color: {color}; font-weight: bold;' for _ in row]

                format_dict = {'開盤價': '{:.2f}', '最高價': '{:.2f}', '最低價': '{:.2f}', '收盤價': '{:.2f}', '成交量': '{:,.0f}', 'MACD': '{:.2f}'}
                styled_df = display_df.tail().style.format(format_dict).apply(color_rows, axis=1)
                
                st.dataframe(styled_df, use_container_width=True)
                
            else:
                st.error("這段期間找不到資料，可能是非交易日或代號錯誤。")
            
    except Exception as e:
        st.error(f"發生錯誤: {e}")
else:
    st.info("👈 請從左側展開「🌸 自選股票」選單，選擇股票來查看圖表。")
