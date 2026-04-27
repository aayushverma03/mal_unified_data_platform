# Mal Unified Payments Pipeline

![CI](https://github.com/aayushverma03/mal_unified_data_platform/actions/workflows/ci.yml/badge.svg)

> Three product squads (Cards, Transfers, Bill Payments) shipping inconsistent
> payment events. One canonical model. Quarantine-pattern validation, integer
> minor units, lifecycle reconstruction via `correlation_id`. Runs locally in
> 30 seconds.

## Quickstart

**macOS / Linux** (with `make`):

```bash
git clone <repo-url> mal-payments-pipeline
cd mal-payments-pipeline
make install       # sets up .venv, installs deps
make seed          # generates 3 squad CSVs in data/raw/
make run           # ingests, adapts, validates, writes Parquet
make query         # runs all 5 demo SQL queries against DuckDB
```

**Windows** (no `make`):

```powershell
git clone <repo-url> mal-payments-pipeline
cd mal-payments-pipeline
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
python -m mal_payments.run seed
python -m mal_payments.run ingest
```

Optional:

```bash
make migrate       # demonstrates v1 to v2 schema migration
make test          # runs the test suite
make dashboard     # launches Streamlit data quality dashboard
make report        # builds the static GitHub Pages report
```

**Requirements:** Python 3.9+ (tested on 3.9 and 3.11). No Docker required.

## Architecture

```
data/raw/cards.csv         |
data/raw/transfers.csv     |--> adapters/  --> validation  --> data/output/canonical/   (Parquet, partitioned)
data/raw/bill_pmts.csv     |    (Pydantic v2)               --> data/output/quarantine/ (rejected + reasons)
                                                                     |
                                                                     --> DuckDB (5 demo SQL queries)
```

Each squad's CSV has its own naming, status vocabulary, amount format, and
timestamp convention, modeling realistic schema divergence. Adapters
normalize to a single canonical event model. Bad rows quarantine instead of
killing the batch.

## The canonical schema (in 4 ideas)

1. **Event-grain, not payment-grain.** `auth`, `capture`, and `refund` are
   one logical payment but three events. `correlation_id` stitches them.
2. **Integer minor units.** No floats. Reconciliation depends on this.
3. **`raw_payload` preserved on every row.** Squads keep their data; nothing
   is lost in normalization. Political feature, not just technical.
4. **`payment_method_details` as a JSON bag.** New payment types add an
   adapter, not a schema change.

See [`src/mal_payments/schema/canonical_v2.py`](src/mal_payments/schema/canonical_v2.py)
for the model, and [PROJECT_BRIEF.md](PROJECT_BRIEF.md) for design context.

## What's where

| Path | Purpose |
|---|---|
| `src/mal_payments/schema/` | Canonical v1 (legacy) and v2 (current) Pydantic models, plus migration |
| `src/mal_payments/adapters/` | One per squad. CSV row in, canonical dict out |
| `src/mal_payments/pipeline.py` | Orchestrates ingest, adapt, validate, write |
| `src/mal_payments/validation.py` | Quarantine-pattern validator |
| `src/mal_payments/mock_data.py` | Generates the 3 mock CSVs (seed=42, idempotent) |
| `src/mal_payments/run.py` | CLI entry point (`python -m mal_payments.run`) |
| `data/raw/` | The 3 mock squad CSVs (committed) |
| `data/output/` | Pipeline outputs (gitignored, regenerated) |
| `sql/` | 5 demo queries showing downstream consumer use cases |
| `tests/` | Schema, adapters, validation, migration tests |
| `dashboard/` | Streamlit data quality monitoring (Deliverable 3) |
| `docs/report.qmd` | Quarto source for the static GitHub Pages demo |

## Design decisions

- **No orchestrator.** 500-line cap and local-runnable constraint.
  Production would use Dagster, flagged in D2.
- **Quarantine, not fail-fast validation.** A bad row from one squad never
  blocks the others.
- **Integer minor units.** The v1 to v2 migration story is the cautionary tale.
- **`correlation_id` everywhere.** Lifecycle reconstruction without it is
  brittle JOIN-on-best-guess.
- **`raw_payload` on every row.** Squads keep their fields; auditability
  for free.

## Live demos

- **Static report (always-on):** <https://aayushverma03.github.io/mal_unified_data_platform/>.
  Quarto-rendered page showing sample canonical records, all 5 SQL
  outputs as charts, and the quarantine breakdown. Re-rendered on every
  push to `main` via `.github/workflows/pages.yml`. Source:
  [`docs/report.qmd`](docs/report.qmd).
- **Interactive dashboard (D3):** [Streamlit Cloud link]. Data-quality
  monitoring (separate deliverable in `dashboard/`).

> GitHub Pages is the insurance. Streamlit apps go to sleep and sometimes
> fail to wake; a static site does not.

## Production gaps (intentionally cut from this implementation)

For 100K transactions per day the missing pieces are: real orchestration
(Dagster), CDC ingestion (Debezium and Kafka), customer identity resolution,
PII tokenization, schema registry, and multi-region DR. These are detailed
in the architecture doc (D2).

---

This is **Deliverable 1** of a 3-part take-home. See `docs/architecture.pdf`
for D2 (architecture and migration strategy) and `dashboard/` for D3 (data
quality monitoring).
