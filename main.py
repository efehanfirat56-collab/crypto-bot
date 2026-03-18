import requests
import time
import os
import threading
from flask import Flask, request

TOKEN = "8330248406:AAGkRbWFts1Ly_Ho0BoI4Zxilc-q5qh_KPw"
TELEGRAM = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

subscribers = set()
last_call = 0

MIDAS_COINS = [
"btc","eth","sol","near","rndr","inj","arb",
"sei","tia","apt","sui","op",
"matic","avax","link","ton","kas","rave"
]

BINANCE_COINS = []


# SAFE REQUEST
def safe(url, params=None):
    global last_call
    try:
        if time.time() - last_call < 0.7:
            time.sleep(0.7)
        last_call = time.time()
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


# TELEGRAM
def send(chat, text):
    try:
        requests.post(f"{TELEGRAM}/sendMessage",
        json={"chat_id": chat, "text": text}, timeout=10)
    except:
        pass


# LOAD BINANCE
def load_binance():
    global BINANCE_COINS
    data = safe("https://api.binance.com/api/v3/exchangeInfo")

    if data:
        BINANCE_COINS = list(set([
            s["baseAsset"].lower()
            for s in data["symbols"]
            if s["quoteAsset"] == "USDT"
        ]))
    else:
        BINANCE_COINS = MIDAS_COINS


load_binance()


# PRICE DATA
def get_prices(symbol):
    try:
        data = safe(
            "https://api.binance.com/api/v3/klines",
            {
                "symbol": symbol.upper()+"USDT",
                "interval": "1m",
                "limit": 100
            }
        )
        if not data:
            return None

        prices = [float(x[4]) for x in data]
        volumes = [float(x[5]) for x in data]

        return prices, volumes
    except:
        return None


# RSI
def rsi(p):
    gains, losses = [], []
    for i in range(1,len(p)):
        diff = p[i]-p[i-1]
        if diff>0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    avg_gain = sum(gains[-14:])/14 if gains else 0
    avg_loss = sum(losses[-14:])/14 if losses else 1

    rs = avg_gain/avg_loss
    return 100-(100/(1+rs))


# EMA
def ema(p,n):
    return sum(p[-n:])/n if len(p)>=n else 0


# MACD
def macd(p):
    return ema(p,12)-ema(p,26)


# CORE ANALYSIS
def analyze(symbol):

    data = get_prices(symbol)

    if not data:
        return None

    prices, volumes = data

    if len(prices) < 50:
        return None

    price = prices[-1]
    r = rsi(prices)
    m = macd(prices)

    score = 0
    reasons = []

    # RSI
    if r < 30:
        score += 25
        reasons.append("Dip (RSI düşük)")

    # MACD
    if m > 0:
        score += 15
        reasons.append("Trend yukarı")

    # MOMENTUM
    if prices[-1] > prices[-5]*1.02:
        score += 20
        reasons.append("Momentum artıyor")

    # BREAKOUT
    if price > max(prices[-20:]):
        score += 20
        reasons.append("Direnç kırıldı")

    # WHALE
    avg_vol = sum(volumes[:-1])/len(volumes[:-1])
    if volumes[-1] > avg_vol*2:
        score += 20
        reasons.append("Whale girişi")

    # FAKE PUMP FILTER
    if prices[-1] > prices[-2]*1.05 and volumes[-1] < avg_vol:
        score -= 25
        reasons.append("Fake pump şüphesi")

    # MIDAS BOOST
    if symbol in MIDAS_COINS:
        score += 10

    # SIGNAL
    if score >= 75:
        signal = "AL 🚀"
    elif score >= 55:
        signal = "İZLE 👀"
    else:
        signal = "RİSKLİ ⚠️"

    return {
        "symbol": symbol,
        "price": round(price,4),
        "rsi": round(r,2),
        "score": score,
        "signal": signal,
        "reasons": reasons
    }


# SCAN SYSTEM
def scan():

    coins = MIDAS_COINS + BINANCE_COINS[:80]

    results = []

    for coin in coins:
        d = analyze(coin)

        if d and d["score"] >= 60:
            results.append(d)

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    return results


# AUTO SYSTEM
def auto():

    sent = set()

    while True:
        try:
            results = scan()

            for r in results[:3]:

                key = r["symbol"]

                if key in sent:
                    continue

                sent.add(key)

                text = f"""
🚨 FIRSAT COIN

🪙 {r['symbol'].upper()}
⭐ SCORE: {r['score']}/100
💰 {r['price']}
📊 RSI {r['rsi']}

📢 {r['signal']}

🔎 {" | ".join(r['reasons'])}
"""

                for u in subscribers:
                    send(u, text)

        except:
            pass

        time.sleep(120)


# MARKET
def market():
    data = safe("https://api.coingecko.com/api/v3/global")

    if not data:
        return "Market alınamadı"

    m = data["data"]

    return f"""
🌍 MARKET

💰 Cap: {round(m['total_market_cap']['usd']/1e9,2)}B
🟡 BTC: %{round(m['market_cap_percentage']['btc'],2)}
"""


# WEBHOOK
@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.json

    if "message" not in data:
        return "ok"

    msg = data["message"]

    chat = msg["chat"]["id"]
    text = msg.get("text","").lower()

    subscribers.add(chat)

    if text == "/start":
        send(chat,
"""🤖 CRYPTO AI BOT

/coin btc
/scan
/market
""")

    elif text == "/scan":
        results = scan()

        if not results:
            send(chat,"Fırsat yok ❌")

        for r in results[:5]:
            send(chat, f"{r['symbol']} → {r['score']}")

    elif text.startswith("/coin"):
        try:
            coin = text.split(" ")[1]
            r = analyze(coin)
            send(chat, str(r))
        except:
            send(chat,"/coin btc")

    elif text == "/market":
        send(chat, market())

    else:
        r = analyze(text)
        if r:
            send(chat, str(r))

    return "ok"


@app.route("/")
def home():
    return "BOT ACTIVE"


threading.Thread(target=auto, daemon=True).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
