import yfinance as yf
import pandas as pd
import datetime
import requests
import json

# ==========================================
# === 1. 基本設定與 Webhook ===
# ==========================================
# 請將下面雙引號內的文字完整替換成你的 Teams 專屬 Webhook 網址
TEAMS_WEBHOOK_URL = "https://default54eb9440cf0345fe835e61bd4ce515.c8.environment.api.powerplatform.com:443/powerautomate/automations/direct/cu/14/workflows/4f478f5755a2464f9cd9e6484979f296/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=zMCuosswuPQ1CRTAaB1XMyCT6aRcBgAQyIxL7EDTP-Q"

# 觀察清單
TARGET_STOCKS = ["2327.TW", "2330.TW", "2317.TW", "2454.TW"]
STOCK_NAMES = {"2327.TW": "國巨", "2330.TW": "台積電", "2317.TW": "鴻海", "2454.TW": "聯發科"}

def format_ticker(ticker):
    name = STOCK_NAMES.get(ticker, "")
    return f"{ticker} ({name})" if name else ticker

# ==========================================
# === 2. 抓取美股數據 ===
# ==========================================
def get_us_market_context():
    print("正在抓取美股收盤數據...")
    sox_hist = yf.Ticker("^SOX").history(period="5d")
    tsm_hist = yf.Ticker("TSM").history(period="5d")
    
    sox_change = 0.0
    tsm_change = 0.0
    
    if len(sox_hist) >= 2:
        sox_change = ((sox_hist['Close'].iloc[-1] - sox_hist['Close'].iloc[-2]) / sox_hist['Close'].iloc[-2]) * 100
    if len(tsm_hist) >= 2:
        tsm_change = ((tsm_hist['Close'].iloc[-1] - tsm_hist['Close'].iloc[-2]) / tsm_hist['Close'].iloc[-2]) * 100
        
    return sox_change, tsm_change

# ==========================================
# === 3. 台股個股決策運算 ===
# ==========================================
def generate_stock_advice(ticker, sox_change):
    try:
        df = yf.Ticker(ticker).history(period="3mo")
        if df.empty: return f"**{format_ticker(ticker)}**：⚠️ 無法取得歷史資料"
        
        last_c = df['Close'].iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        
        tr = pd.concat([
            df['High'] - df['Low'],
            (df['High'] - df['Close'].shift()).abs(),
            (df['Low'] - df['Close'].shift()).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        if sox_change >= 1.0 and last_c > ma20:
            verdict = "🟢 今日建議買進"
            in_low = round(last_c, 2)
            in_high = round(last_c + (atr * 0.3), 2)
            entry = f"{in_low} ~ {in_high} (小幅回踩試單)"
            target = round(last_c + (atr * 1.5), 2)
            stop = round(last_c - (atr * 0.8), 2)
        elif sox_change <= -1.0 and last_c > ma20:
            verdict = "🟡 盤中拉回低接"
            in_low = round(last_c - (atr * 0.8), 2)
            in_high = round(last_c - (atr * 0.3), 2)
            entry = f"{in_low} ~ {in_high} (逢低掛單低接)"
            target = round(last_c + (atr * 1.0), 2)
            stop = round(ma20 * 0.98, 2)
        elif last_c < ma20 and sox_change <= 0:
            verdict = "⚪ 今日建議觀望"
            entry = "暫無建議進場點"
            target = "-"
            stop = "-"
        else:
            verdict = "🔴 逢高減碼獲利"
            entry = "不建議買入"
            target = round(last_c + (atr * 0.8), 2)
            stop = round(ma20, 2)
            
        return f"**{format_ticker(ticker)}**：{verdict}\n\n📍 進場：{entry} | 🎯 目標：{target} | 🛑 停損：{stop}"
    except Exception as e:
        return f"**{format_ticker(ticker)}**：⚠️ 計算錯誤"

# ==========================================
# === 4. 組裝訊息並發送至 Teams ===
# ==========================================
def send_to_teams():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    sox_change, tsm_change = get_us_market_context()
    
    # 組合 Markdown 訊息
    message_text = f"### 🤖 晨間 AI 盤前決策報告 ({now_str})\n\n"
    message_text += f"**🇺🇸 隔夜美股關鍵指標**\n\n"
    message_text += f"- 費城半導體 (SOX)：`{sox_change:+.2f}%`\n\n"
    message_text += f"- 台積電 ADR：`{tsm_change:+.2f}%`\n\n"
    message_text += f"---\n\n**🎯 個股今日操作指引**\n\n"
    
    for ticker in TARGET_STOCKS:
        advice = generate_stock_advice(ticker, sox_change)
        if advice:
            message_text += f"- {advice}\n\n"
            
    if "你的_teams_webhook_網址" in TEAMS_WEBHOOK_URL or not TEAMS_WEBHOOK_URL.startswith("http"):
        print("\n⚠️ 【注意】您尚未填入正確的 Teams Webhook 網址！\n")
        return

    # 【關鍵修改】：換成微軟新版 Workflows 專用的 Adaptive Card (適應性卡片) 格式
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": message_text,
                            "wrap": True
                        }
                    ]
                }
            }
        ]
    }
    
    headers = {'Content-Type': 'application/json'}
    response = requests.post(TEAMS_WEBHOOK_URL, headers=headers, data=json.dumps(payload))
    
    # 【關鍵修改】：把 202 (Accepted) 也視為成功！
    if response.status_code in [200, 202]:
        print(f"✅ 成功發送至 Teams 頻道！(伺服器回應碼：{response.status_code})")
    else:
        print(f"❌ 發送失敗，錯誤碼：{response.status_code}")
        print(f"錯誤訊息：{response.text}")

if __name__ == "__main__":
    send_to_teams()
