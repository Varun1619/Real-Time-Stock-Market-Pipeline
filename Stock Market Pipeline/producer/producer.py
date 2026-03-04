import finnhub, json, time, os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

client  = finnhub.Client(api_key=os.getenv("FINNHUB_API_KEY"))
OUT_DIR = Path("landing_zone")
TICKERS = ["AAPL", "MSFT", "TSLA", "AMZN", "GOOGL", "META"]

OUT_DIR.mkdir(exist_ok=True)

def fetch_and_save(ticker):
    quote = client.quote(ticker)

    # Detect empty or bad response
    if not quote or quote.get("c", 0) == 0:
        print(f"No data returned for {ticker}, skipping.")
        return

    record = {
        "ticker":  ticker,
        "open":    quote["o"],
        "close":   quote["c"],
        "high":    quote["h"],
        "low":     quote["l"],
        "prev_close": quote["pc"],
        "ts":      quote["t"]
    }

    fname = OUT_DIR / f"{ticker}_{int(time.time())}.json"
    fname.write_text(json.dumps(record))
    print(f"Saved {fname} | {ticker} @ ${quote['c']}")

while True:
    for t in TICKERS:
        try:
            fetch_and_save(t)
            time.sleep(1)  # 1 second between calls, well within 60/min limit
        except Exception as e:
            print(f"Error for {t}: {e}")
    print(f"Cycle complete. Sleeping 60s...")
    time.sleep(60)