-- 01_daily_volume_by_payment_type.sql
--
-- Question: How does daily payment volume break down across our three
--           payment types over the last 30 days?
-- Persona:  Exec dashboard / weekly business review.
-- Output:   one row per (event_date, payment_type) with counts and
--           USD-equivalent gross volume.
--
-- Run:
--   duckdb -c "$(cat sql/01_daily_volume_by_payment_type.sql)"
--
-- This is the simplest cross-product aggregate the canonical model
-- enables. Pre-platform, finance had to JOIN three squad-specific
-- tables with three different schemas to get this view.

SELECT
    DATE_TRUNC('day', event_timestamp)        AS event_date,
    payment_type,
    COUNT(*)                                  AS event_count,
    SUM(amount_usd_minor) / 100.0             AS gross_volume_usd,
    COUNT(DISTINCT customer_id)               AS distinct_customers
FROM read_parquet('data/output/canonical/**/*.parquet')
WHERE status = 'settled'
  AND event_timestamp >= CURRENT_DATE - INTERVAL 30 DAY
GROUP BY 1, 2
ORDER BY 1 DESC, 2;
