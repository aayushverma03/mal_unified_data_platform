-- 02_failure_breakdown_by_squad.sql
--
-- Question: Which squads are seeing the highest failure rates and what
--           are the dominant failure reasons in the last 7 days?
-- Persona:  Platform reliability / on-call rotation.
-- Output:   one row per (source_squad, status_reason) sorted by failure count.
--
-- The status_reason field carries decline codes (cards: 05, 51, 14),
-- transfer return codes, and bill_payment failure reasons — all
-- normalized into a single column. Pre-platform, each squad had its
-- own failure-code vocabulary in its own table.

WITH last_7d AS (
    SELECT *
    FROM read_parquet('data/output/canonical/**/*.parquet')
    WHERE event_timestamp >= CURRENT_DATE - INTERVAL 7 DAY
)
SELECT
    source_squad,
    COALESCE(status_reason, '(none)')         AS status_reason,
    COUNT(*) FILTER (WHERE status = 'failed') AS failures,
    COUNT(*)                                  AS total_events,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE status = 'failed') / COUNT(*),
        2
    )                                         AS failure_rate_pct
FROM last_7d
GROUP BY 1, 2
HAVING COUNT(*) FILTER (WHERE status = 'failed') > 0
ORDER BY failures DESC
LIMIT 50;
