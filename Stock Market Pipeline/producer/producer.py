import requests, json, time, os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
API_KEY  = os.getenv("ALPHA_VANTAGE_API_KEY")
OUT_DIR  = Path("landing_zone")
TICKERS  = ["AAPL", "MSFT", "TSLA", "AMZN"]

OUT_DIR.mkdir(exist_ok=True)

def fetch_and_save(ticker):
    url = (f"https://www.alphavantage.co/query"
           f"?function=TIME_SERIES_INTRADAY"
           f"&symbol={ticker}&interval=1min&apikey={API_KEY}")
    data = requests.get(url, timeout=10).json()
    record = {"ticker": ticker, "payload": data, "ts": time.time()}
    fname  = OUT_DIR / f"{ticker}_{int(time.time())}.json"
    fname.write_text(json.dumps(record))
    print(f"Saved {fname}")

while True:
    for t in TICKERS:
        try:
            fetch_and_save(t)
        except Exception as e:
            print(f"Error for {t}: {e}")
    time.sleep(60)