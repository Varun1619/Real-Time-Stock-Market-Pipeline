{{ config(
    materialized='table',
    file_format='delta'
) }}

SELECT
    ticker,
    ts,
    close,
    ROUND(AVG(close) OVER (
        PARTITION BY ticker
        ORDER BY ts
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 4) AS ma_7,
    ROUND(AVG(close) OVER (
        PARTITION BY ticker
        ORDER BY ts
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ), 4) AS ma_30
FROM {{ source('stock_data', 'stock_silver') }}
ORDER BY ticker, ts