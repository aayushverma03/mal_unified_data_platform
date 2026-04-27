# PROJECT_BRIEF.md — Mal Take-Home

Project context. The README is the reviewer's entry point; this file
explains the *why* behind the design choices.

## The company (assumed context)

Mal is a UAE-based neobank with Islamic banking products. Three product
squads own three payment surfaces:

- **Cards** — debit/credit card transactions, auth + capture lifecycle
- **Transfers** — domestic + international wires, P2P, remittance
  corridors (UAE→IN, UAE→PH, UAE→PK are real expat-driven flows)
- **Bill Payments** — utilities, telecom, government, scheduled vs.
  one-off

Each squad has built its own pipeline. Schemas have diverged.
Cross-product analytics, finance reconciliation, and CBUAE regulatory
reporting all suffer.

## The role

Senior Data Engineering. The take-home is judged on:

1. Platform thinking — reusability, extensibility
2. Cross-team collaboration — adoption, resistance handling
3. Technical correctness — schema, pipeline, production-readiness
4. Impact orientation — metrics, pragmatic execution
5. Bonus: payments / neobanking domain knowledge

## The 3 deliverables

| # | Deliverable | Format | Scope |
|---|---|---|---|
| 1 | Build challenge — unified pipeline | GitHub repo + optional demo | This repo |
| 2 | Architecture & migration strategy | PDF, 3–4 pages | `docs/architecture.pdf` |
| 3 | Data quality monitoring | GitHub repo or live URL | `dashboard/` folder, Streamlit |

This file scopes Deliverable 1. D2 and D3 are separate work products
that build on the choices made here.

## Why each design choice matters in Mal context

- **Integer minor units** — finance reconciliation breaks under float.
  Real pain in any payments org; bigger pain in a young neobank without
  legacy reconciliation tools.
- **`correlation_id` for lifecycle** — auth/capture/refund is one
  logical payment but multiple events. Fraud and finance both need to
  reconstruct the lifecycle.
- **`raw_payload` preservation** — squads will resist platform
  migration if they think they "lose" their data. Keeping the raw
  record is a political feature as much as a technical one.
- **Quarantine validation** — a single bad row from one squad cannot
  block the others. This is the cross-team-collaboration signal.
- **UAE remittance corridors in mock data** — Mal's real customer base
  is heavily expat. Showing INR/PHP/PKR destination accounts signals
  you understand who the customers actually are.
- **MCC + biller_category capture** — enables halal-spending
  classification downstream, which matters for an Islamic banking
  product. One canonical schema, multiple Sharia-relevant products
  built on top.

## Out of scope for D1 (cut intentionally — defended in D2 §5)

- Real orchestration (would use Dagster in production)
- CDC / streaming ingestion (would use Debezium → Kafka)
- Customer identity resolution (would route through identity service)
- PII tokenization (would use a vault)
- Schema registry (would use Confluent or Git-based)
- Multi-region / DR (UAE data residency rules require it)

## Hosting

- **GitHub repo** — required, source of truth
- **GitHub Pages** — Quarto-rendered static report; always-on; bulletproof
- **Streamlit Cloud** — D3 interactive dashboard; click-around demo

GitHub Pages is the insurance. Streamlit apps go to sleep and
sometimes fail to wake; a static site does not.
