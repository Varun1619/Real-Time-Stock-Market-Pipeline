# Real-Time Stock Market Pipeline

A production-style data engineering pipeline that ingests live stock market data via the Alpha Vantage API, streams it into Databricks using Auto Loader, stores it in a Delta Lake medallion architecture (Bronze, Silver, Gold), transforms it with dbt, and orchestrates the entire workflow with Apache Airflow.

Built as a portfolio project to demonstrate end-to-end data engineering skills across streaming ingestion, lakehouse storage, SQL transformation, data quality testing, and pipeline orchestration.

> No Docker. No Kafka. No virtualization required. Runs entirely on a local Python environment and Databricks Community Edition (free).

---

## Architecture

```
Alpha Vantage API
      │
      ▼
Python Producer (local)
writes JSON files every 60s to landing_zone/
      │
      ▼
Databricks Auto Loader
monitors landing_zone/, streams new files automatically
      │
      ▼
Delta Lake Bronze   (raw, append only)
      │
      ▼
Delta Lake Silver   (cleaned, deduplicated, validated)
      │
      ▼
Delta Lake Gold     (aggregated, business ready)
      │
      ▼
dbt Models          (SQL transforms, tests, lineage docs)
      │
      ▼
Apache Airflow DAG  (daily orchestration of Silver → Gold → dbt)
```

**Key design decision:** Auto Loader replaces Kafka entirely. It is a native Databricks feature that continuously monitors a directory for new files and ingests them as a stream. It is production-grade, requires zero infrastructure setup, and is a highly relevant skill for Databricks-focused data engineering roles.

---

## Tech Stack

| Layer | Tool | Version | Why |
|---|---|---|---|
| Data Source | Alpha Vantage API | Free tier | Real intraday stock data, 500 calls/day |
| Ingestion | Databricks Auto Loader | Built in | Native streaming ingestion, replaces Kafka |
| Processing | Apache Spark / PySpark | 3.5+ | Core of Databricks, required skill |
| Storage | Delta Lake | 3.x | ACID transactions, MERGE, time travel |
| Compute | Databricks Community Edition | Latest | Free managed Spark environment |
| Transformation | dbt Core | 1.8+ | SQL transforms with testing and lineage |
| Orchestration | Apache Airflow | 2.9+ | Most common orchestrator in job listings |
| Environment | Conda | Latest | Dependency isolation without virtualization |

---

## Project Structure

```
stock-market-pipeline/
├── producer/
│   └── producer.py                # Polls Alpha Vantage, writes JSON to landing_zone/
├── landing_zone/                  # Auto Loader watches this directory
├── notebooks/
│   ├── 01_bronze_ingest.ipynb     # Auto Loader → Bronze Delta table
│   ├── 02_silver_transform.ipynb  # Clean, dedup, validate → Silver Delta table
│   └── 03_gold_aggregate.ipynb    # Optional batch aggregations
├── dbt_project/
│   ├── models/
│   │   ├── silver/
│   │   │   └── silver_stock_quotes.sql
│   │   └── gold/
│   │       ├── gold_daily_summary.sql
│   │       └── gold_moving_averages.sql
│   ├── tests/
│   │   └── schema.yml
│   └── dbt_project.yml
├── airflow/
│   └── stock_pipeline_dag.py
├── docs/
│   └── architecture.png
├── .env.example
├── requirements.txt
└── README.md
```

---

## Prerequisites

- Python 3.10 or higher
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) installed
- Free [Databricks Community Edition](https://community.cloud.databricks.com) account
- Free [Alpha Vantage API key](https://www.alphavantage.co/support/#api-key)

No Docker. No Java. No virtualization required.

---

## Setup and Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/stock-market-pipeline.git
cd stock-market-pipeline
```

### 2. Create a single conda environment

Because Kafka has been removed from the stack, all tools can coexist in one environment without dependency conflicts.

```bash
conda create -n stock-pipeline python=3.10 -y
conda activate stock-pipeline
pip install -r requirements.txt
```

**requirements.txt:**
```
requests==2.31.0
python-dotenv==1.0.0
dbt-core==1.8.0
dbt-spark==1.8.0
apache-airflow==2.9.0
apache-airflow-providers-databricks==6.0.0
pandas==2.1.0
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
ALPHA_VANTAGE_API_KEY=your_key_here
DATABRICKS_HOST=https://community.cloud.databricks.com
DATABRICKS_TOKEN=your_databricks_token
```

### 4. Run the producer

```bash
python producer/producer.py
```

The producer polls Alpha Vantage every 60 seconds and writes one JSON file per ticker to `landing_zone/`. Leave this running in a terminal while working in Databricks.

### 5. Upload landing_zone to Databricks DBFS

In the Databricks UI go to Data → DBFS → upload the `landing_zone/` folder, or use the Databricks CLI:

```bash
pip install databricks-cli
databricks configure --token
databricks fs mkdirs dbfs:/landing_zone
databricks fs cp landing_zone/ dbfs:/landing_zone --recursive
```

### 6. Import and run notebooks in Databricks

Upload each notebook from `/notebooks` to your Databricks workspace. Run them in order:

1. `01_bronze_ingest.ipynb` — starts the Auto Loader streaming job
2. `02_silver_transform.ipynb` — run once Bronze has data
3. `03_gold_aggregate.ipynb` — optional, dbt handles most Gold logic

### 7. Configure and run dbt

```bash
cd dbt_project
dbt debug         # verify Databricks connection
dbt run           # execute all models
dbt test          # run data quality tests
dbt docs generate && dbt docs serve   # open lineage graph in browser
```

### 8. Start Airflow

```bash
export AIRFLOW_HOME=~/airflow
airflow db init
airflow users create \
  --username admin --password admin \
  --firstname Admin --lastname User \
  --role Admin --email admin@example.com
airflow scheduler &
airflow webserver --port 8080
```

Copy `airflow/stock_pipeline_dag.py` to `~/airflow/dags/` and trigger the DAG from `localhost:8080`.

---

## Delta Lake Medallion Architecture

### Bronze (Raw)
Auto Loader appends every incoming JSON file as a row. No filtering or transformation. Full source fidelity is preserved. An `ingested_at` timestamp is added for auditability.

Schema: `ticker, open, close, high, low, volume, ts, source_file, ingested_at`

### Silver (Cleaned)
Deduplicated on `(ticker, ts)`. Nulls on critical columns are dropped. A derived `price_range` column (high minus low) is added. Records are upserted with Delta MERGE to prevent duplicates on reruns. A `processed_at` column tracks transformation time.

Schema: `ticker, open, close, high, low, volume, price_range, ts, ingested_at, processed_at`

### Gold (Aggregated)
Business-ready tables built by dbt models. Two models ship with this project:

**gold_daily_summary** — avg close, max high, min low, total volume per ticker per day

**gold_moving_averages** — 7-day and 30-day rolling averages per ticker using window functions

---

## Auto Loader Notebook (Bronze Ingestion)

```python
from pyspark.sql.functions import current_timestamp, input_file_name

df_stream = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", "/checkpoints/schema")
    .load("dbfs:/landing_zone/")
    .withColumn("ingested_at", current_timestamp())
    .withColumn("source_file", input_file_name())
)

(df_stream.writeStream
    .format("delta")
    .option("checkpointLocation", "/checkpoints/bronze")
    .outputMode("append")
    .start("/delta/bronze/stock_quotes")
)
```

---

## dbt Models

**gold_daily_summary.sql:**

```sql
SELECT
    ticker,
    DATE(ts)       AS trade_date,
    AVG(close)     AS avg_close,
    MAX(high)      AS daily_high,
    MIN(low)       AS daily_low,
    SUM(volume)    AS total_volume,
    COUNT(*)       AS record_count
FROM {{ ref('silver_stock_quotes') }}
GROUP BY 1, 2
```

**gold_moving_averages.sql:**

```sql
SELECT
    ticker,
    ts,
    close,
    AVG(close) OVER (
        PARTITION BY ticker
        ORDER BY ts
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS ma_7d,
    AVG(close) OVER (
        PARTITION BY ticker
        ORDER BY ts
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) AS ma_30d
FROM {{ ref('silver_stock_quotes') }}
```

---

## dbt Tests

Defined in `tests/schema.yml`:

- `not_null` on ticker, close, ts
- `unique` on (ticker, trade_date) in the Gold summary model
- `accepted_values` for ticker against known ticker list
- Custom test asserting close is always greater than 0

---

## Airflow DAG Overview

```
trigger_silver_notebook
        │
        ▼
trigger_gold_notebook
        │
        ▼
    dbt_run
        │
        ▼
   dbt_test
```

The producer runs continuously as a background process. Airflow manages the daily batch transformation layer only.

---

## Known Limitations

- Alpha Vantage free tier allows 5 requests per minute and 500 per day. The producer respects this with a 60-second interval and a small ticker list.
- Databricks Community Edition clusters auto-terminate after 2 hours of inactivity. The Auto Loader streaming job will need to be restarted after termination.
- `landing_zone/` files must be synced to DBFS manually or via the Databricks CLI. A production version would use cloud storage (S3, ADLS, GCS) that Auto Loader monitors natively.
- No visualization layer is included. Apache Superset can be added as a free BI layer on top of the Gold tables.

---

## What This Project Demonstrates

- Streaming ingestion using Databricks Auto Loader (cloudFiles format)
- Delta Lake ACID transactions, MERGE operations, and the medallion architecture
- PySpark Structured Streaming with schema inference and checkpointing
- dbt for SQL-based transformation, testing, and data lineage documentation
- Apache Airflow DAG design with task dependencies and failure handling
- Clean dependency management using conda without Docker or virtualization
- Separation of continuous ingestion from scheduled batch transformation

---

## Future Improvements

- Add Great Expectations for deeper data quality profiling on Silver and Gold layers
- Provision Databricks resources with Terraform for infrastructure as code
- Move `landing_zone/` to cloud object storage (S3 or ADLS) for native Auto Loader integration
- Add an Apache Superset dashboard on top of Gold tables
- Schedule the producer as an Airflow task instead of running it manually

---

## License

MIT License. Free to use and adapt for learning and portfolio purposes.