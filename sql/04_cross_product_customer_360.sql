-- 04_cross_product_customer_360.sql
--
-- Question: Top 20 customers by total activity across all 3 payment
--           types — one row per customer with counts and amounts per
--           product.
-- Persona:  Customer Success / VIP segmentation / cross-sell signals.
-- Output:   one row per customer with pivoted per-product columns.
--
-- This is the FLAGSHIP query for the canonical model. Pre-platform,
-- producing this view required three squad-specific extracts plus
-- manual customer-id reconciliation (cards used customer_ref, the
-- others used customer_id) — a multi-day analyst task. With the
-- canonical model: one query.

WITH per_customer AS (
    SELECT
        customer_id,
        payment_type,
        COUNT(*) AS event_count,
        SUM(amount_usd_minor) / 100.0 AS volume_usd
    FROM read_parquet('data/output/canonical/**/*.parquet')
    WHERE status = 'settled'
    GROUP BY 1, 2
)
SELECT
    customer_id,
    COALESCE(SUM(event_count) FILTER (WHERE payment_type = 'card'),         0) AS card_events,
    COALESCE(SUM(volume_usd)  FILTER (WHERE payment_type = 'card'),         0) AS card_volume_usd,
    COALESCE(SUM(event_count) FILTER (WHERE payment_type = 'transfer'),     0) AS transfer_events,
    COALESCE(SUM(volume_usd)  FILTER (WHERE payment_type = 'transfer'),     0) AS transfer_volume_usd,
    COALESCE(SUM(event_count) FILTER (WHERE payment_type = 'bill_payment'), 0) AS bill_events,
    COALESCE(SUM(volume_usd)  FILTER (WHERE payment_type = 'bill_payment'), 0) AS bill_volume_usd,
    SUM(event_count)                                                           AS total_events,
    SUM(volume_usd)                                                            AS total_volume_usd,
    -- "Cross-product" customers are an early loyalty signal
    COUNT(DISTINCT payment_type)                                               AS products_used
FROM per_customer
GROUP BY customer_id
ORDER BY total_volume_usd DESC
LIMIT 20;
