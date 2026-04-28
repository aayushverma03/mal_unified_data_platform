# Mal Payments Data Quality Dashboard (D3)

Streamlit app that monitors the canonical event store for data-quality
signals platform reliability cares about: per-squad ingestion volume,
quarantine rate and reasons, schema-vocabulary drift, and incomplete
lifecycle chains (auth without capture, pending transfers, overdue bills).

This is the operational counterpart to D1's analyst report. D1 answers
"what is the data telling us about customers and revenue?" and D3 answers
"is the pipeline healthy and is each squad's data showing up cleanly?".

## Run locally

From the repo root:

```bash
make install
make seed     # generates the 3 mock CSVs
make run      # ingests, validates, writes Parquet
make dashboard
```

Or directly:

```bash
uv run streamlit run dashboard/app.py
```

The app opens at <http://localhost:8501>. If you have not run `seed` and
`ingest` yet, the app auto-runs them on first load so you are never
looking at an empty dashboard.

## Deploy to Streamlit Cloud

1. Sign in at <https://streamlit.io/cloud> with your GitHub account.
2. Click "New app" and pick this repository.
3. Set the main file path to `dashboard/app.py`.
4. Set the Python version to 3.11.
5. Streamlit Cloud reads `requirements.txt` from the repo root, which
   already has `streamlit`, `polars`, `duckdb`, `plotly`, and the
   `mal_payments` package itself (installed via `pyproject.toml`).
6. Click "Deploy".

The mock CSVs live in `data/raw/` and are committed, so the dashboard
runs end-to-end on Streamlit Cloud without any extra setup. The app
auto-runs `seed` and `ingest` if the canonical Parquet output is missing
on cold start.

Once deployed, copy the public URL into the root README's "Live demos"
section.

## What the dashboard shows

| Tab | Purpose |
|---|---|
| Overview | Daily ingestion volume per squad, status mix per squad, USD volume share per payment type |
| Quarantine | Quarantine rate, error-class breakdown, recent bad rows with their original payload and validation error |
| Schema drift | Distributions of status, event_type, and currency vocabularies. New values appearing here are early signals a squad shipped a schema change without telling the platform |
| Lifecycle | Incomplete event chains: cards authorised but not captured, transfers stuck pending, scheduled bills past their date |
| Explorer | Sample recent events. Toggle to inspect the raw_payload column for any row |

## Adding new data-quality checks

The whole app is one file (`app.py`). Each tab is a `with tab_X:` block.
To add a new check:

1. Pick the tab it belongs in (Overview for headline KPIs, Schema drift
   for vocabulary checks, Lifecycle for chain-completeness checks).
2. Compute the metric from the cached `fdf` dataframe (filtered by the
   sidebar) or from `fqdf` (filtered quarantine).
3. Render with `st.metric`, `st.dataframe`, or a Plotly chart wrapped in
   the `_style()` helper for consistent typography.
