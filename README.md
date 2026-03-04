# Real-Time Stock Market Pipeline

A production-style data engineering pipeline that ingests live stock market data, streams it through Apache Kafka, processes it in Databricks using PySpark Structured Streaming, stores it in a Delta Lake medallion architecture, transforms it with dbt, and orchestrates the entire workflow with Apache Airflow.

Built as a portfolio project to demonstrate end-to-end data engineering skills across streaming, batch, lakehouse, and orchestration patterns.

---

## Architecture

```
Alpha Vantage API
      │
      ▼
Kafka Producer (Python)
      │
      ▼
Kafka Topic: stock_quotes
      │
      ▼
Databricks Structured Streaming
      │
      ▼
Delta Lake Bronze  →  Silver  →  Gold
                                  │
                                  ▼
                              dbt Models
                                  │
                                  ▼
                           Apache Airflow DAG
```

**Data flow summary:**
A Python producer polls the Alpha Vantage API every 60 seconds for intraday quotes on selected tickers (AAPL, MSFT, TSLA, AMZN) and publishes each record as JSON to a Kafka topic. Databricks consumes the stream in real time and lands raw records into the Bronze Delta table. Scheduled Airflow jobs then trigger Silver cleaning, Gold aggregation, and dbt transformation runs daily.

---

## Tech Stack

| Layer | Tool | Version | Why |
|---|---|---|---|
| Data Source | Alpha Vantage API | Free tier | Real intraday stock data, 500 calls/day |
| Streaming | Apache Kafka | 3.x (via Docker) | Industry standard message bus |
| Processing | Apache Spark / PySpark | 3.5+ | Core of Databricks, required skill |
| Storage | Delta Lake | 3.x | ACID transactions on the lakehouse |
| Compute | Databricks Community Edition | Latest | Free managed Spark environment |
| Transformation | dbt Core | 1.8+ | SQL transformations with testing and lineage |
| Orchestration | Apache Airflow | 2.9+ | Most common orchestrator in job listings |
| Containerization | Docker | Latest | Local Kafka without cloud costs |

---

## Project Structure

```
stock-market-pipeline/
├── producer/
│   └── kafka_producer.py          # Polls Alpha Vantage, publishes to Kafka
├── notebooks/
│   ├── 01_bronze_ingest.ipynb     # Structured Streaming → Bronze Delta table
│   ├── 02_silver_transform.ipynb  # Dedup, clean, validate → Silver Delta table
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
│   └── stock_pipeline_dag.py      # Full DAG with Databricks + dbt tasks
├── docker/
│   └── docker-compose.yml         # Kafka + Zookeeper local setup
├── docs/
│   └── architecture.png
└── README.md
```

---

## Prerequisites

- Python 3.10 or higher
- Docker Desktop installed and running
- Free [Databricks Community Edition](https://community.cloud.databricks.com) account
- Free [Alpha Vantage API key](https://www.alphavantage.co/support/#api-key)

---

## Setup and Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/stock-market-pipeline.git
cd stock-market-pipeline
```

### 2. Create a Python virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**requirements.txt includes:**
```
kafka-python==2.0.2
requests==2.31.0
dbt-core==1.8.0
dbt-spark==1.8.0
apache-airflow==2.9.0
apache-airflow-providers-databricks==6.0.0
pandas==2.1.0
```

### 3. Start Kafka with Docker

```bash
cd docker
docker-compose up -d
```

This spins up Zookeeper and a Kafka broker on `localhost:9092`.

Create the topic:

```bash
docker exec -it kafka kafka-topics.sh \
  --create \
  --topic stock_quotes \
  --partitions 3 \
  --replication-factor 1 \
  --bootstrap-server localhost:9092
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```
ALPHA_VANTAGE_API_KEY=your_key_here
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
DATABRICKS_HOST=https://community.cloud.databricks.com
DATABRICKS_TOKEN=your_databricks_token
```

### 5. Run the Kafka producer

```bash
python producer/kafka_producer.py
```

The producer will poll Alpha Vantage every 60 seconds and publish JSON records to the `stock_quotes` topic.

### 6. Import notebooks into Databricks

Upload each notebook from the `/notebooks` directory to your Databricks Community Edition workspace. Run `01_bronze_ingest.ipynb` first to start the streaming job.

### 7. Configure and run dbt

```bash
cd dbt_project
dbt debug       # verify connection to Databricks
dbt run         # run all models
dbt test        # run data quality tests
dbt docs generate && dbt docs serve   # open lineage docs in browser
```

### 8. Start Airflow

```bash
export AIRFLOW_HOME=~/airflow
airflow db init
airflow users create --username admin --password admin \
  --firstname Admin --lastname User --role Admin --email admin@example.com
airflow scheduler &
airflow webserver --port 8080
```

Copy `airflow/stock_pipeline_dag.py` into `~/airflow/dags/` and trigger the DAG from the Airflow UI at `localhost:8080`.

---

## Delta Lake Medallion Architecture

### Bronze (Raw)
Raw JSON records as they arrive from Kafka. No transformations, no filtering. Full fidelity of the source data is preserved. An `ingested_at` timestamp column is added for auditability.

Schema: `ticker, open, close, high, low, volume, ts, ingested_at`

### Silver (Cleaned)
Deduplicated on `(ticker, ts)`. Null values on critical columns are dropped. A derived `price_range` column (high minus low) is added. Records are upserted using Delta MERGE to prevent duplicates on reruns.

Schema: `ticker, open, close, high, low, volume, price_range, ts, ingested_at, processed_at`

### Gold (Aggregated)
Business-ready tables produced by dbt. Two models:

**gold_daily_summary** — daily aggregations per ticker (avg close, max high, min low, total volume)

**gold_moving_averages** — 7-day and 30-day rolling averages per ticker using window functions

---

## dbt Tests

Tests are defined in `tests/schema.yml` and cover:

- `not_null` on ticker, close, ts columns
- `unique` on the (ticker, trade_date) composite key in the Gold summary model
- `accepted_values` for ticker column against the known ticker list
- Custom test asserting close price is always greater than 0

Run all tests with: `dbt test`

---

## Airflow DAG Overview

The `stock_pipeline_dag.py` DAG runs on a daily schedule and chains the following tasks:

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

The Kafka producer runs as a continuously running background process (separate from the DAG). Airflow manages only the batch transformation layer.

---

## Known Limitations

- Alpha Vantage free tier limits calls to 5 per minute and 500 per day. The producer respects this with a 60-second polling interval and a small ticker list.
- Databricks Community Edition clusters auto-terminate after 2 hours of inactivity. The streaming job will need to be restarted after termination.
- This project runs Kafka locally via Docker. A production version would use Confluent Cloud or Amazon MSK.
- No front-end visualization layer is included. Apache Superset can be added as a free BI layer on top of the Gold tables.

---

## What This Project Demonstrates

- Real-time data ingestion using a Kafka producer and consumer pattern
- PySpark Structured Streaming with schema enforcement and checkpointing
- Delta Lake ACID transactions, MERGE operations, and the medallion architecture
- dbt for SQL-based transformation, testing, and data lineage documentation
- Apache Airflow DAG design with task dependencies and failure handling
- Separation of streaming ingestion from batch transformation (a production best practice)
- Infrastructure as code mindset with Docker for local environment reproducibility

---

## Future Improvements

- Add Great Expectations for deeper data quality profiling on Silver and Gold layers
- Provision Databricks resources with Terraform for full infrastructure as code
- Deploy Kafka to Confluent Cloud free tier to eliminate local Docker dependency
- Add an Apache Superset dashboard on top of Gold tables for visual output
- Containerize the producer with Docker for easier deployment

---

## License

MIT License. Free to use and adapt for learning and portfolio purposes.
