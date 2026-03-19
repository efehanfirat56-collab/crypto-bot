import requests
import time
import os
import threading
from flask import Flask, request

TOKEN = "8330248406:AAGkRbWFts1Ly_Ho0BoI4Zxilc-q5qh_KPw"
TELEGRAM = f"https://api.telegram.org/bot{TOKEN}"

APP_URL = "https://crypto-bot-1-hs1x.onrender.com"

app = Flask(__name__)

subscribers = set()
sent_signals = set()
last_call = 0

MIDAS_COINS = [
"BTC","ETH","SOL","NEAR","RNDR","INJ","ARB",
"SEI","TIA","APT","SUI","OP",
"MATIC","AVAX","LINK","TON","KAS","RAVE"
]

BINANCE_COINS = []


def safe(url, params=None):
    global last_call
    try:
        if time.time() - last_call < 0.6:
            time.sleep(0.6)

        r = requests.get(url, params=params, timeout=10)
        last_call = time.time()

        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def send(chat, text):
    try:
        requests.post(
            f"{TELEGRAM}/sendMessage",
            json={"chat_id": chat, "text": text},
            timeout=10
        )
    except:
        pass


def keep_alive():
    while True:
        try:
            requests.get(APP_URL)
        except:
            pass
        time.sleep(300)


def load_binance():
    global BINANCE_COINS
    data = safe("https://api.binance.com/api/v3/exchangeInfo")

    if data:
        BINANCE_COINS = list(set([
            s["baseAsset"]
            for s in data["symbols"]
            if s["quoteAsset"] == "USDT"
        ]))
    else:
        BINANCE_COINS = MIDAS_COINS


load_binance()


def get_prices(symbol):
    try:
        symbol = symbol.upper() + "USDT"

        data = safe(
            "https://api.binance.com/api/v3/klines",
            {
                "symbol": symbol,
                "interval": "1m",
                "limit": 120
            }
        )

        if not data:
            return None

        prices = [float(x[4]) for x in data]
        volumes = [float(x[5]) for x in data]

        return prices, volumes
    except:
        return None


# 🔥 FALLBACK EKLENDİ
def get_price_fallback(symbol):
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": symbol.lower(),
            "vs_currencies": "usd"
        }

        data = safe(url, params)

        if data and symbol.lower() in data:
            return data[symbol.lower()]["usd"]
    except:
        pass

    return None


def rsi(p):
    gains, losses = [], []
    for i in range(1,len(p)):
        diff = p[i]-p[i-1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    avg_gain = sum(gains[-14:])/14 if gains else 0
    avg_loss = sum(losses[-14:])/14 if losses else 1

    rs = avg_gain/avg_loss
    return 100-(100/(1+rs))


def macd(p):
    return (sum(p[-12:])/12) - (sum(p[-26:])/26)


def analyze(symbol):

    data = get_prices(symbol)

    # 🔥 FALLBACK DEVREYE GİRİYOR
    if not data:
        price = get_price_fallback(symbol)

        if price:
            return f"""
🪙 {symbol.upper()}

💰 ${price}
📊 Basit veri (fallback)
"""
        return f"⚠️ {symbol.upper()} bulunamadı"

    prices, volumes = data

    if len(prices) < 50:
        return "⚠️ Veri yetersiz"

    price = prices[-1]
    r = rsi(prices)
    m = macd(prices)

    score = 0
    reasons = []

    if r < 30:
        score += 25
        reasons.append("RSI dip")

    if m > 0:
        score += 15
        reasons.append("Trend up")

    if prices[-1] > prices[-5]*1.02:
        score += 20
        reasons.append("Momentum")

    if price > max(prices[-20:]):
        score += 20
        reasons.append("Breakout")

    avg_vol = sum(volumes[:-1])/len(volumes[:-1])

    if volumes[-1] > avg_vol*2:
        score += 20
        reasons.append("Whale")

    if prices[-1] > prices[-2]*1.05 and volumes[-1] < avg_vol:
        score -= 25
        reasons.append("Fake pump")

    if symbol.upper() in MIDAS_COINS:
        score += 10

    return f"""
🚨 ANALİZ

🪙 {symbol.upper()}
⭐ {score}/100
💰 {round(price,4)}
📊 RSI {round(r,2)}

🔎 {" | ".join(reasons)}
"""


def scan():
    coins = MIDAS_COINS + BINANCE_COINS[:80]
    results = []

    for c in coins:
        r = analyze(c)

        if "⭐" in str(r):
            score = int(r.split("⭐")[1].split("/")[0])

            if score >= 60:
                results.append((c, r, score))

    return sorted(results, key=lambda x: x[2], reverse=True)[:5]


def auto():
    while True:
        try:
            results = scan()

            for coin, msg, score in results:

                if len(sent_signals) > 50:
                    sent_signals.clear()

                if coin in sent_signals:
                    continue

                sent_signals.add(coin)

                for u in subscribers:
                    send(u, "🚨 FIRSAT\n" + msg)

        except:
            pass

        time.sleep(120)


@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.json

    if "message" not in data:
        return "ok"

    msg = data["message"]
    chat = msg["chat"]["id"]
    text = msg.get("text","").lower().strip()

    subscribers.add(chat)

    if text == "/start":
        send(chat,"Bot aktif 🚀")

    elif text == "/scan":
        results = scan()

        if not results:
            send(chat,"Fırsat yok ❌")

        for _, r, _ in results:
            send(chat, r)

    elif text.startswith("/coin"):
        parts = text.split()

        if len(parts) < 2:
            send(chat,"/coin btc yaz")
        else:
            send(chat, analyze(parts[1]))

    else:
        send(chat, analyze(text))

    return "ok"


@app.route("/")
def home():
    return "BOT ACTIVE"


threading.Thread(target=auto, daemon=True).start()
threading.Thread(target=keep_alive, daemon=True).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
