-- 05_currency_exposure_remittance_corridors.sql
--
-- Question: Weekly transfer volume by destination remittance corridor.
-- Persona:  Treasury / FX desk / Compliance.
-- Output:   one row per (week, destination_country) with counts and AED-
--           equivalent volume.
--
-- UAE-specific: a meaningful share of Mal's transfer volume is expat
-- remittance to home countries (India, Philippines, Pakistan, Bangladesh,
-- Egypt). Corridor-level visibility drives liquidity planning, partner
-- bank selection, and CBUAE reporting.
--
-- Destination country is encoded in the masked to_account prefix
-- (AE, IN, PH, PK, BD, EG). The adapter preserved this via the
-- payment_method_details JSON bag on transfers; we extract here.

WITH transfers AS (
    SELECT
        DATE_TRUNC('week', event_timestamp) AS week_start,
        -- to_account is "IN-***-9920" → take leading 2 chars
        UPPER(SUBSTR(counterparty_id, 1, 2)) AS dest_country,
        amount_minor,
        amount_usd_minor,
        currency
    FROM read_parquet('data/output/canonical/**/*.parquet')
    WHERE payment_type = 'transfer'
      AND status = 'settled'
)
SELECT
    week_start,
    CASE dest_country
        WHEN 'AE' THEN 'UAE (domestic)'
        WHEN 'IN' THEN 'India'
        WHEN 'PH' THEN 'Philippines'
        WHEN 'PK' THEN 'Pakistan'
        WHEN 'BD' THEN 'Bangladesh'
        WHEN 'EG' THEN 'Egypt'
        ELSE 'Other'
    END                                              AS destination,
    COUNT(*)                                         AS transfer_count,
    SUM(amount_usd_minor) / 100.0                    AS volume_usd,
    -- Compliance often wants AED equivalent; approximate via amount_minor
    -- when source currency is AED, else amount_usd_minor * 3.67 (USD→AED peg)
    ROUND(SUM(
        CASE WHEN currency = 'AED'
             THEN amount_minor / 100.0
             ELSE (amount_usd_minor / 100.0) * 3.67
        END
    ), 2)                                            AS volume_aed_equiv
FROM transfers
GROUP BY 1, 2
ORDER BY 1 DESC, volume_usd DESC;
