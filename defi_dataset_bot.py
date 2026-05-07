import requests
import pandas as pd
from datetime import datetime
import time
import os
import base64

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "hugoneuvillepro-web/crypto-premium-dataset"

PROTOCOLS = [
    "uniswap", "aave", "curve", "lido", 
    "makerdao", "compound", "pancakeswap"
]

def get_protocol_tvl(protocol):
    print(f"  Collecte TVL {protocol}...")
    try:
        url = f"https://api.llama.fi/protocol/{protocol}"
        response = requests.get(url, timeout=15).json()
        tvl_data = response.get("tvl", [])
        df = pd.DataFrame(tvl_data)
        df["date"] = pd.to_datetime(df["date"], unit="s").dt.strftime("%Y-%m-%d")
        df = df.rename(columns={"totalLiquidityUSD": "tvl"})
        df["protocol"] = protocol
        df = df[["date", "protocol", "tvl"]].tail(365)
        time.sleep(1)
        print(f"  OK - {protocol}")
        return df
    except Exception as e:
        print(f"  ERREUR {protocol} : {e}")
        return None

def get_defi_overview():
    print("  Collecte overview DeFi...")
    try:
        url = "https://api.llama.fi/protocols"
        response = requests.get(url, timeout=15).json()
        rows = []
        for p in response:
            if p.get("slug") in PROTOCOLS:
                rows.append({
                    "protocol": p.get("slug"),
                    "name": p.get("name"),
                    "tvl_usd": p.get("tvl"),
                    "change_1d": p.get("change_1d"),
                    "change_7d": p.get("change_7d"),
                    "category": p.get("category"),
                    "chains": str(p.get("chains", [])),
                })
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"  ERREUR overview : {e}")
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
            "message": f"Update DeFi dataset {datetime.now().strftime('%Y-%m-%d')}",
            "content": content_b64
        }
        if sha:
            data["sha"] = sha
        response = requests.put(url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            print(f"  OK - {filename} uploade sur GitHub")
        else:
            print(f"  ERREUR GitHub : {response.json()}")
    except Exception as e:
        print(f"  ERREUR GitHub : {e}")

print(f"[{datetime.now().strftime('%H:%M:%S')}] Démarrage dataset DeFi...")

all_tvl = []
for protocol in PROTOCOLS:
    df = get_protocol_tvl(protocol)
    if df is not None:
        all_tvl.append(df)

if all_tvl:
    tvl_df = pd.concat(all_tvl, ignore_index=True)
    tvl_df = tvl_df.sort_values(["protocol", "date"]).reset_index(drop=True)
    tvl_df.to_csv("defi_tvl_dataset_latest.csv", index=False)
    print(f"{len(tvl_df)} lignes TVL historique")
    upload_to_github("defi_tvl_dataset_latest.csv", "defi_tvl_dataset_latest.csv")

overview = get_defi_overview()
if overview is not None:
    overview.to_csv("defi_overview_latest.csv", index=False)
    print(f"{len(overview)} protocoles dans l'overview")
    upload_to_github("defi_overview_latest.csv", "defi_overview_latest.csv")

print("Terminé !")
