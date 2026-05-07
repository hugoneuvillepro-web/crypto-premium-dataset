import os
import ccxt
import pandas as pd
import requests
from datetime import datetime
import base64

COINS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT", "AVAX/USDT"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "hugoneuvillepro-web/crypto-premium-dataset"

def get_ohlcv(symbol):
    coin_ids = {
        "BTC/USDT": "bitcoin",
        "ETH/USDT": "ethereum",
        "SOL/USDT": "solana",
        "BNB/USDT": "binancecoin",
        "XRP/USDT": "ripple",
        "ADA/USDT": "cardano",
        "AVAX/USDT": "avalanche-2",
    }
    
    coin_id = coin_ids[symbol]
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=365"
        response = requests.get(url, timeout=15).json()
        df = pd.DataFrame(response, columns=["timestamp", "open", "high", "low", "close"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms").dt.strftime("%Y-%m-%d")
        df["volume"] = None
        df["symbol"] = symbol.replace("/USDT", "")
        df.drop("timestamp", axis=1, inplace=True)
        df = df.groupby("date").last().reset_index()
        return df
    except Exception as e:
        print(f"ERREUR {symbol} : {e}")
        return None

def add_indicators(df):
    try:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        df["rsi"] = 100 - (100 / (1 + gain / loss))
        df["ema21"] = df["close"].ewm(span=21).mean()
        df["ema50"] = df["close"].ewm(span=50).mean()
        ema12 = df["close"].ewm(span=12).mean()
        ema26 = df["close"].ewm(span=26).mean()
        df["macd"] = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        sma20 = df["close"].rolling(20).mean()
        std20 = df["close"].rolling(20).std()
        df["bb_upper"] = sma20 + 2 * std20
        df["bb_lower"] = sma20 - 2 * std20
        return df
    except Exception as e:
        print(f"ERREUR indicateurs : {e}")
        return df

def get_fear_greed():
    try:
        url = "https://api.alternative.me/fng/?limit=365"
        response = requests.get(url, timeout=10).json()
        df = pd.DataFrame(response["data"])[["timestamp", "value", "value_classification"]]
        df["date"] = pd.to_datetime(df["timestamp"].astype(int), unit="s").dt.strftime("%Y-%m-%d")
        df.rename(columns={"value": "fear_greed", "value_classification": "fear_greed_label"}, inplace=True)
        df.drop("timestamp", axis=1, inplace=True)
        return df
    except:
        return None

def get_btc_dominance():
    try:
        url = "https://api.coingecko.com/api/v3/global"
        response = requests.get(url, timeout=10).json()
        return round(response["data"]["market_cap_percentage"]["btc"], 2)
    except:
        return None

def get_funding_rate(symbol):
    try:
        exchange = ccxt.binance({"options": {"defaultType": "future"}})
        funding = exchange.fetch_funding_rate(symbol)
        return round(funding["fundingRate"] * 100, 4)
    except:
        return None

def upload_to_github(filepath, filename):
    try:
        with open(filepath, "r") as f:
            content = f.read()
        content_b64 = base64.b64encode(content.encode()).decode()
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        get_response = requests.get(url, headers=headers).json()
        sha = get_response.get("sha", None)
        data = {
            "message": f"Update dataset {datetime.now().strftime('%Y-%m-%d')}",
            "content": content_b64
        }
        if sha:
            data["sha"] = sha
        response = requests.put(url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            print("Upload GitHub OK")
        else:
            print(f"ERREUR GitHub : {response.json()}")
    except Exception as e:
        print(f"ERREUR GitHub : {e}")

print(f"[{datetime.now().strftime('%H:%M:%S')}] Démarrage...")
fg = get_fear_greed()
dominance = get_btc_dominance()
all_dfs = []
for symbol in COINS:
    df = get_ohlcv(symbol)
    if df is None:
        continue
    df = add_indicators(df)
    if fg is not None:
        df = df.merge(fg, on="date", how="left")
    df["btc_dominance"] = dominance
    df["funding_rate"] = get_funding_rate(symbol)
    all_dfs.append(df)

final = pd.concat(all_dfs, ignore_index=True)
final = final.sort_values(["symbol", "date"]).reset_index(drop=True)
filepath = "crypto_premium_dataset_latest.csv"
final.to_csv(filepath, index=False)
print(f"{len(final)} lignes, {len(final.columns)} colonnes")
upload_to_github(filepath, "crypto_premium_dataset_latest.csv")
print("Terminé !")
