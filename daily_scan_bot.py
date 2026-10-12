import yfinance as yf
import pandas as pd
import requests
import json
import datetime
import os

==========================================

⚙️ 基本設定與全域變數

==========================================

目標掃描清單

TARGET_STOCKS = ["2327.TW", "2330.TW", "2454.TW"]

🔴 請將這裡換成你的 Teams Webhook URL

💡 進階技巧：未來部署到 GitHub Actions 時，建議改用 os.getenv("TEAMS_WEBHOOK_URL") 讀取 Secret

WEBHOOK_URL = "https://default54eb9440cf0345fe835e61bd4ce515.c8.environment.api.powerplatform.com:443/powerautomate/automations/direct/cu/14/workflows/4f478f5755a2464f9cd9e6484979f296/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=zMCuosswuPQ1CRTAaB1XMyCT6aRcBgAQyIxL7EDTP-Q"

設定台北時區 (GitHub 伺服器預設為 UTC 英國時間，必須強制轉換為台北時間)

TPE_TZ = datetime.timezone(datetime.timedelta(hours=8))
TODAY_STR = datetime.datetime.now(TPE_TZ).strftime("%Y-%m-%d")

記憶檔路徑，用來記錄今天推播過的股票，避免洗版

LOG_FILE = "alert_history.json"

==========================================

💰 模組 1：真實法人籌碼抓取 (FinMind API)

==========================================

def fetch_institutional_chips(ticker):
"""抓取近 15 日法人籌碼，並回傳格式化字串供 Teams 推播使用"""
stock_id = ticker.split('.')[0]
start_date = (datetime.datetime.now(TPE_TZ) - datetime.timedelta(days=15)).strftime("%Y-%m-%d")
url = "https://api.finmindtrade.com/api/v4/data"
parameter = {
"dataset": "TaiwanStockInstitutionalInvestorsBuySell",
"data_id": stock_id,
"start_date": start_date
}

try:
    response = requests.get(url, params=parameter)
    data = response.json()
    
    if data.get("msg") == "success" and len(data.get("data", [])) > 0:
        df = pd.DataFrame(data["data"])
        name_mapping = {
            'Foreign_Investor': '外資',
            'Investment_Trust': '投信',
        }
        df['name'] = df['name'].map(name_mapping)
        df_filtered = df[df['name'].isin(['外資', '投信'])].copy()
        
        if not df_filtered.empty:
            df_filtered['買賣超(張)'] = (df_filtered['buy'] - df_filtered['sell']) // 1000
            
            # 計算近期總和
            recent_foreign = df_filtered[df_filtered['name'] == '外資']['買賣超(張)'].sum()
            recent_trust = df_filtered[df_filtered['name'] == '投信']['買賣超(張)'].sum()
            
            return f"外資近15日動向: {recent_foreign:,} 張\n投信近15日動向: {recent_trust:,} 張"
except Exception as e:
    print(f"[{ticker}] 籌碼抓取失敗: {e}")
    
return "今日暫無籌碼數據或抓取失敗"


==========================================

📲 模組 2：Teams 推播通訊

==========================================

def send_teams_alert(ticker, current_price, status, advice, chip_summary):
"""發送精美的 MessageCard 到 Teams 頻道"""
payload = {
"@type": "MessageCard",
"@context": "http://schema.org/extensions",
"themeColor": "E24A4A" if "跌破" in status else "28A745",
"summary": f"🔔 {ticker} 策略觸發通知",
"sections": [{
"activityTitle": f"📈 量化系統警報：{ticker}",
"activitySubtitle": f"⏱️ 9:20 開盤區間突破 (ORB) 策略觸發",
"facts": [
{"name": "即時狀態", "value": status},
{"name": "觸發市價", "value": f"{current_price} 元"},
{"name": "系統建議", "value": advice},
{"name": "籌碼透視", "value": chip_summary}
],
"markdown": True
}]
}
headers = {'Content-Type': 'application/json'}
try:
requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(payload))
print(f"✅ 成功發送 {ticker} 訊號至 Teams！")
except Exception as e:
print(f"❌ 發送 {ticker} Teams 訊號失敗: {e}")

==========================================

🧠 模組 3：讀取與寫入推播紀錄 (防洗版機制)

==========================================

def load_alert_history():
if os.path.exists(LOG_FILE):
try:
with open(LOG_FILE, "r") as f:
return json.load(f)
except:
return {}
return {}

def save_alert_history(history):
with open(LOG_FILE, "w") as f:
json.dump(history, f)

==========================================

🚀 主程式：每日早盤掃描引擎

==========================================

def main():
print(f"🤖 啟動每日早盤掃描機器人 - 執行日期: {TODAY_STR}")

# 讀取歷史推播紀錄
alert_history = load_alert_history()
if TODAY_STR not in alert_history:
    alert_history[TODAY_STR] = [] # 初始化今日的清單
    
for ticker in TARGET_STOCKS:
    print(f"🔍 正在分析 {ticker}...")
    
    # 檢查今天是否已經推播過了
    if ticker in alert_history[TODAY_STR]:
        print(f"⚠️ {ticker} 今日已發送過警報，跳過處理。")
        continue
        
    try:
        # 抓取今日 5 分 K 線
        stock = yf.Ticker(ticker)
        df = stock.history(period="1d", interval="5m")
        
        # 確保資料量足夠 (至少要過 9:20，也就是第 4 根 K 線)
        if not df.empty and len(df) >= 4:
            morning_range = df.iloc[:4]
            orb_high = morning_range['High'].max()
            orb_low = morning_range['Low'].min()
            current_price = df['Close'].iloc[-1]
            
            status = ""
            advice = ""
            
            # 判斷是否突破或跌破
            if current_price > orb_high:
                status = "🟢 強勢突破早盤高點"
                advice = f"主力拉抬，市價已突破 9:20 高點 **{orb_high:.2f}** 元。建議拉回不破可偏多佈局。"
            elif current_price < orb_low:
                status = "🔴 弱勢跌破早盤低點"
                advice = f"賣壓沉重，市價已跌穿 9:20 低點 **{orb_low:.2f}** 元。建議空手觀望或順勢偏空。"
                
            # 如果有產生訊號，則執行籌碼抓取與推播
            if status != "":
                chip_summary = fetch_institutional_chips(ticker)
                send_teams_alert(ticker, current_price, status, advice, chip_summary)
                
                # 記錄起來，今天不再重複推播
                alert_history[TODAY_STR].append(ticker)
                save_alert_history(alert_history)
            else:
                print(f"[{ticker}] 目前在 9:20 區間內震盪 ({orb_low:.2f} ~ {orb_high:.2f})，無訊號。")
        else:
            print(f"[{ticker}] 數據不足，可能尚未開盤或抓取不到今日資料。")
            
    except Exception as e:
        print(f"❌ 處理 {ticker} 時發生錯誤: {e}")
        
print("🏁 今日掃描任務結束。")


if name == "main":
main()
