-- 03_authorization_to_settlement_latency.sql
--
-- Question: For card transactions, what is the latency between auth
--           and capture (settlement)? p50 / p95 / p99.
-- Persona:  Cards squad reliability + Platform SLA review.
-- Output:   single row with percentile latencies in seconds.
--
-- This query demonstrates the value of event-grain modeling +
-- correlation_id: the auth event and the capture event are separate
-- rows linked by correlation_id. Pre-platform, latency required
-- joining two squad-specific tables on a string match.
--
-- Note: card_capture's initiated_at is the auth time (carried forward
-- from the auth event's adapter logic), and completed_at is the capture
-- time. The diff is the auth→settlement latency.

WITH captures AS (
    SELECT
        correlation_id,
        EXTRACT(EPOCH FROM (completed_at - initiated_at)) AS latency_seconds
    FROM read_parquet('data/output/canonical/**/*.parquet')
    WHERE payment_type = 'card'
      AND event_type = 'card_capture'
      AND completed_at IS NOT NULL
      AND initiated_at IS NOT NULL
)
SELECT
    COUNT(*)                                              AS captured_events,
    ROUND(MIN(latency_seconds), 2)                        AS min_seconds,
    ROUND(QUANTILE_CONT(latency_seconds, 0.50), 2)        AS p50_seconds,
    ROUND(QUANTILE_CONT(latency_seconds, 0.95), 2)        AS p95_seconds,
    ROUND(QUANTILE_CONT(latency_seconds, 0.99), 2)        AS p99_seconds,
    ROUND(MAX(latency_seconds), 2)                        AS max_seconds
FROM captures;
