import requests
import random
import time
import os
from flask import Flask, request
from threading import Thread

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


def safe_request(url, params=None):
    global last_call
    try:
        now = time.time()
        if now - last_call < 1:
            time.sleep(1)

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


def load_binance():
    global BINANCE_COINS
    try:
        data = safe_request("https://api.binance.com/api/v3/exchangeInfo")
        coins = set()

        if data:
            for s in data["symbols"]:
                if s["quoteAsset"] == "USDT":
                    coins.add(s["baseAsset"].lower())

        BINANCE_COINS = list(coins)

    except:
        BINANCE_COINS = MIDAS_COINS


load_binance()


def get_prices(symbol):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": symbol.upper() + "USDT",
            "interval": "1h",
            "limit": 50
        }

        data = safe_request(url, params)
        if not data:
            return None

        return [float(x[4]) for x in data]
    except:
        return None


def coingecko_price(symbol):
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": symbol,
            "vs_currencies": "usd"
        }

        data = safe_request(url, params)
        if data and symbol in data:
            return data[symbol]["usd"]
    except:
        pass

    return None


def rsi(prices):
    gains = []
    losses = []

    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]

        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    avg_gain = sum(gains)/14 if gains else 0
    avg_loss = sum(losses)/14 if losses else 1

    rs = avg_gain / avg_loss
    return 100 - (100/(1+rs))


def macd(prices):
    ema12 = sum(prices[-12:]) / 12
    ema26 = sum(prices[-26:]) / 26
    return ema12 - ema26


def analysis(symbol):
    prices = get_prices(symbol)

    if prices:
        r = rsi(prices)
        m = macd(prices)

        price = prices[-1]

        entry = round(price * 0.98, 4)
        tp = round(price * 1.05, 4)
        sl = round(price * 0.95, 4)

        pump = min(int(abs(m)*10 + r/2), 100)

        yorum = random.choice([
            "Trend güçleniyor",
            "Hacim artışı var",
            "Volatil hareket beklenebilir",
            "Alıcılar güçlü"
        ])

        return f"""
📊 ALTCOIN ANALİZ

🪙 {symbol.upper()}

RSI: {round(r,2)}
MACD: {round(m,4)}

🚀 Pump %{pump}

💰 Entry {entry}
🎯 TP {tp}
🛑 SL {sl}

📊 Yorum:
{yorum}
"""

    price = coingecko_price(symbol)

    if price:
        return f"""
📊 COIN ANALİZ

🪙 {symbol.upper()}

💰 Fiyat ${price}
"""

    return "⚠️ Coin bulunamadı"


def market():
    data = safe_request("https://api.coingecko.com/api/v3/global")

    if not data:
        return "⚠️ Veri alınamadı"

    m = data["data"]

    cap = m["total_market_cap"]["usd"]
    btc = m["market_cap_percentage"]["btc"]

    return f"""
🌍 MARKET

💰 MarketCap ${round(cap/1e9,2)}B
🟡 BTC dominance %{round(btc,2)}
"""


def signal():
    coin = random.choice(MIDAS_COINS)
    return f"""
🚨 MIDAS SIGNAL

🪙 {coin.upper()}

Momentum artışı
"""


def opportunity():
    coin = random.choice(MIDAS_COINS)
    return f"""
💎 FIRSAT COIN

🪙 {coin.upper()}

AI fırsat
"""


def trending():
    data = safe_request("https://api.coingecko.com/api/v3/search/trending")

    if not data:
        return "Trend alınamadı"

    text = "🔥 TRENDING\n\n"

    for c in data["coins"][:5]:
        text += c["item"]["name"] + "\n"

    return text


def movers():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency":"usd","order":"percent_change_24h_desc","per_page":5}

    data = safe_request(url, params)

    if not data:
        return "Veri alınamadı"

    text = "📈 TOP GAINERS\n\n"

    for c in data:
        text += f"{c['name']} %{round(c['price_change_percentage_24h'],2)}\n"

    return text


def auto_alert():
    while True:
        try:
            coin = random.choice(MIDAS_COINS)
            prices = get_prices(coin)

            if prices:
                r = rsi(prices)

                if r < 35:
                    msg = f"""
🚨 FIRSAT

🪙 {coin.upper()}

RSI aşırı satım
"""
                    for u in subscribers:
                        send(u, msg)

        except:
            pass

        time.sleep(300)


Thread(target=auto_alert, daemon=True).start()


@app.route("/")
def home():
    return "BOT ACTIVE"


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json

        if "message" not in data:
            return "ok"

        msg = data["message"]
        chat = msg["chat"]["id"]
        text = msg.get("text","").lower()

        subscribers.add(chat)

        if text == "/start":
            send(chat,
"""🤖 CRYPTO SCOUT PRO

/coin btc
/analysis sol
/market
/signal
/opportunity
/trending
/movers
""")

        elif text.startswith("/coin"):
            coin = text.split(" ")[1]
            send(chat, analysis(coin))

        elif text.startswith("/analysis"):
            coin = text.split(" ")[1]
            send(chat, analysis(coin))

        elif text == "/market":
            send(chat, market())

        elif text == "/signal":
            send(chat, signal())

        elif text == "/opportunity":
            send(chat, opportunity())

        elif text == "/trending":
            send(chat, trending())

        elif text == "/movers":
            send(chat, movers())

        else:
            send(chat, analysis(text))

    except:
        pass

    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
