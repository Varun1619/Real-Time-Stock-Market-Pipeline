# 📈 Real-Time Stock Market Pipeline

A data engineering portfolio project that ingests live stock market data, processes it through a medallion architecture in Databricks, transforms it with dbt, and orchestrates it with Apache Airflow.

> Built entirely on free tools. No Docker. No Kafka. No virtualization required.

---

## 🏗️ Architecture

```
Finnhub API (free tier)
      │
      ▼
🐍 Python Producer
   writes JSON files every 60s → landing_zone/
      │
      ▼
📦 Databricks Volume (Unity Catalog)
   manual upload via Databricks UI
      │
      ▼
⚡ Databricks Auto Loader (cloudFiles)
   streams new files → Bronze Delta table
      │
      ▼
🥉 Bronze Table — raw, append only
      │
      ▼
🥈 Silver Table — cleaned, deduped, enriched
      │
      ▼
🥇 dbt Gold Models — aggregated, business ready
      │
      ▼
🎯 Apache Airflow — orchestrates dbt daily
```

---

## 🛠️ Tech Stack

| Tool | Purpose | Free |
|---|---|---|
| Finnhub API | Live stock data source | ✅ 60 calls/min |
| Databricks Community Edition | Spark compute and storage | ✅ Always free |
| Delta Lake | ACID storage, medallion layers | ✅ Built into Databricks |
| Databricks Auto Loader | Streaming file ingestion | ✅ Built into Databricks |
| Unity Catalog Volumes | File storage for raw JSON | ✅ Built into Databricks |
| dbt Core | SQL transformations and testing | ✅ Open source |
| Apache Airflow | Pipeline orchestration | ✅ Open source |
| Conda | Dependency management | ✅ Free |

---

## 📁 Project Structure

```
stock-market-pipeline/
├── producer/
│   └── producer.py              # Polls Finnhub, writes JSON to landing_zone/
├── landing_zone/
│   └── .gitkeep                 # Raw JSON files live here locally (gitignored)
├── notebooks/
│   ├── 01_bronze_ingest.ipynb   # Auto Loader → Bronze managed table
│   └── 02_silver_transform.ipynb # Clean, dedup → Silver managed table
├── dbt_project/
│   ├── models/
│   │   ├── sources.yml
│   │   └── gold/
│   │       ├── schema.yml
│   │       ├── gold_daily_summary.sql
│   │       └── gold_moving_averages.sql
│   └── dbt_project.yml
├── airflow/
│   └── stock_pipeline_dag.py
├── docs/
│   └── architecture.png
├── .env.example
├── .gitignore
└── README.md
```

---

## ⚙️ Setup

### Prerequisites
- Python 3.10+
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- Free [Databricks Community Edition](https://community.cloud.databricks.com) account
- Free [Finnhub API key](https://finnhub.io)

### Install dependencies

```bash
conda create -n stock-pipeline python=3.10 -y
conda activate stock-pipeline
pip install finnhub-python python-dotenv dbt-databricks apache-airflow apache-airflow-providers-databricks
```

### Configure environment

```bash
cp .env.example .env
```

```
FINNHUB_API_KEY=your_key_here
DATABRICKS_HOST=https://community.cloud.databricks.com
```

### Run the producer

```bash
python producer/producer.py
```

Files will appear in `landing_zone/` every 60 seconds. Upload them manually to your Databricks Volume via the UI.

---

## 🔄 Pipeline Layers

### 🥉 Bronze
Raw JSON records ingested by Auto Loader using `trigger(availableNow=True)`. Appended as a managed Delta table in Unity Catalog. Fields: `ticker, open, close, high, low, prev_close, ts, ingested_at, source_file`

### 🥈 Silver
Deduplicates on `(ticker, ts)`, drops nulls and zero prices, and adds three derived columns:
- `price_range` — intraday volatility (high minus low)
- `price_change` — daily movement (close minus prev_close)
- `pct_change` — percentage move vs previous close

### 🥇 Gold (dbt)
Two models built on top of Silver:
- `gold_daily_summary` — avg close, high, low, price range per ticker per day
- `gold_moving_averages` — 7-day and 30-day rolling averages per ticker

---

## 🧪 dbt Tests

```bash
dbt run     # build Gold models
dbt test    # run data quality checks
dbt docs generate && dbt docs serve  # view lineage graph at localhost:8080
```

Tests cover `not_null` on all critical columns and `accepted_values` on the ticker column.

---

## ⚠️ Known Limitations

| Limitation | Reason |
|---|---|
| **No Kafka** | Requires Java and Docker, neither available in this environment. Replaced with Databricks Auto Loader which provides the same streaming guarantee natively. |
| **No Docker** | System does not support virtualization. All tools run natively via conda. |
| **No Personal Access Token** | Not available on Databricks Community Edition. Authentication uses OAuth via browser. |
| **Manual file upload to DBFS** | Community Edition does not support programmatic CLI access. Files are uploaded manually via the Databricks UI to a Unity Catalog Volume. |
| **No continuous streaming** | `INFINITE_STREAMING_TRIGGER` is not supported on Community Edition clusters. `trigger(availableNow=True)` is used instead, processing all new files in a single batch. |
| **Finnhub free tier** | Capped at 60 API calls per minute. Producer uses a 60-second cycle with 6 tickers staying well within limits. Alpha Vantage was originally planned but only allows 25 calls per day. |

---

## 🚀 Future Improvements

- Move `landing_zone/` to cloud object storage (S3 or ADLS) for native Auto Loader monitoring without manual uploads
- Add Great Expectations for deeper data quality profiling
- Provision infrastructure with Terraform
- Add Apache Superset dashboard on top of Gold tables
- Upgrade to paid Databricks tier to enable continuous streaming and PAT authentication

---

## 📄 License

MIT — free to use and adapt for learning and portfolio purposes.