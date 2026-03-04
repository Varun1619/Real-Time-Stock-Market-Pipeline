{{ config(
    materialized='table',
    file_format='delta'
) }}

SELECT
    ticker,
    DATE(ts) AS trade_date,
    ROUND(AVG(close), 4) AS avg_close,
    MAX(high) AS daily_high,
    MIN(low) AS daily_low,
    ROUND(MAX(price_range), 4) AS max_price_range,
    ROUND(AVG(pct_change), 4) AS avg_pct_change,
    COUNT(*) AS record_count
FROM {{ source('stock_data', 'stock_silver') }}
GROUP BY 1, 2
ORDER BY 1, 2