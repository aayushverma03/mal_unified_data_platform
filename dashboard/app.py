"""Mal Payments Data Quality Dashboard. Streamlit app for D3.

Run locally:  uv run streamlit run dashboard/app.py
Cloud deploy: see dashboard/README.md.

Data sources:
  - data/output/canonical/  (canonical Parquet, partitioned)
  - data/output/quarantine/ (per-run JSON files with bad rows + errors)

If those are missing on first run (Streamlit Cloud cold start), the app
auto-runs `seed` and `ingest` so the dashboard is never empty.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import polars as pl
import streamlit as st

# Repo root resolution. Streamlit Cloud sets cwd to the repo root, but
# local invocations may differ.
HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data"
CANONICAL = DATA / "output" / "canonical"
QUARANTINE = DATA / "output" / "quarantine"

PALETTE = {"cards": "#ef4444", "transfers": "#2563eb", "bill_payments": "#10b981"}
PT_PALETTE = {"card": "#ef4444", "transfer": "#2563eb", "bill_payment": "#10b981"}
TEMPLATE = "plotly_white"


def _ensure_data() -> None:
    """Auto-seed and ingest if outputs are missing (cold start)."""
    if any(CANONICAL.glob("**/*.parquet")):
        return
    from mal_payments.mock_data import seed
    from mal_payments.pipeline import ingest

    seed(ROOT)
    ingest(ROOT)


@st.cache_data(ttl=300)
def load_canonical() -> pl.DataFrame:
    _ensure_data()
    return pl.read_parquet(str(CANONICAL / "**" / "*.parquet"))


@st.cache_data(ttl=300)
def load_quarantine() -> pd.DataFrame:
    rows = []
    if QUARANTINE.exists():
        for run_dir in sorted(QUARANTINE.iterdir()):
            run_ts = run_dir.name
            for f in run_dir.glob("*.json"):
                squad = f.stem
                for entry in json.loads(f.read_text()):
                    err = entry["error"].split("\n")[0]
                    err_class = (
                        "Pydantic ValidationError"
                        if err.startswith("1 validation error")
                        else err[:90]
                    )
                    rows.append({
                        "run_ts": run_ts,
                        "squad": squad,
                        "error_class": err_class,
                        "error": entry["error"],
                        "raw": json.dumps(entry["raw"], default=str)[:200],
                    })
    return pd.DataFrame(rows)


def _style(fig, height=380):
    fig.update_layout(
        template=TEMPLATE, height=height,
        margin=dict(l=30, r=20, t=50, b=30),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color="#1f2937"),
        title_font=dict(size=15, color="#0f172a"),
    )
    return fig


# -----------------------------------------------------------------------------
# Page setup
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Mal Payments Data Quality",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {padding-top:1.5rem; padding-bottom:2rem;}
[data-testid="stMetricValue"] {font-size:2rem; font-weight:600; color:#0f172a;}
[data-testid="stMetricLabel"] {font-size:0.85rem; color:#64748b;}
h1 {letter-spacing:-0.02em;}
h2 {letter-spacing:-0.015em; margin-top:1rem;}
</style>
""", unsafe_allow_html=True)

st.title("Mal Payments Data Quality")
st.caption("Platform reliability view. Per-squad ingestion, quarantine, and schema-drift monitoring on top of the canonical event store.")

with st.spinner("Loading canonical event store..."):
    df = load_canonical()
    qdf = load_quarantine()

# -----------------------------------------------------------------------------
# Sidebar filters
# -----------------------------------------------------------------------------

with st.sidebar:
    st.header("Filters")
    pdf = df.to_pandas()
    pdf["event_timestamp"] = pd.to_datetime(pdf["event_timestamp"])

    min_d = pdf["event_timestamp"].min().date()
    max_d = pdf["event_timestamp"].max().date()
    date_range = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range
    else:
        start_d, end_d = min_d, max_d

    squads = st.multiselect(
        "Source squad",
        options=sorted(pdf["source_squad"].unique()),
        default=sorted(pdf["source_squad"].unique()),
    )
    statuses = st.multiselect(
        "Status",
        options=sorted(pdf["status"].unique()),
        default=sorted(pdf["status"].unique()),
    )
    st.caption(f"Pipeline: mal_payments v0.2.0")
    st.caption(f"Source: {CANONICAL}")
    if st.button("Reload data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

mask = (
    (pdf["event_timestamp"].dt.date >= start_d)
    & (pdf["event_timestamp"].dt.date <= end_d)
    & (pdf["source_squad"].isin(squads))
    & (pdf["status"].isin(statuses))
)
fdf = pdf.loc[mask].copy()
fqdf = qdf[qdf["squad"].isin(squads)] if not qdf.empty and squads else qdf

# -----------------------------------------------------------------------------
# Header metrics
# -----------------------------------------------------------------------------

total = len(fdf)
settled = (fdf["status"] == "settled").sum()
quar = len(fqdf)
input_total = total + quar
qrate = (quar / input_total * 100) if input_total else 0.0
distinct = fdf["customer_id"].nunique()
last_seen = fdf["event_timestamp"].max() if total else None

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Canonical events", f"{total:,}")
c2.metric("Settled", f"{settled:,}", f"{(settled/total*100 if total else 0):.1f}%")
c3.metric("Quarantined", f"{quar:,}", f"{qrate:.2f}%", delta_color="inverse")
c4.metric("Distinct customers", f"{distinct:,}")
c5.metric("Latest event", last_seen.strftime("%Y-%m-%d %H:%M") if last_seen is not None else "no data")

st.divider()

# -----------------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------------

tab_overview, tab_quar, tab_drift, tab_lifecycle, tab_explore = st.tabs(
    ["Overview", "Quarantine", "Schema drift", "Lifecycle", "Explorer"]
)

# --- Overview --------------------------------------------------------

with tab_overview:
    st.subheader("Ingestion timeline")
    daily = (
        fdf.assign(d=fdf["event_timestamp"].dt.date)
        .groupby(["d", "source_squad"]).size().reset_index(name="events")
    )
    fig = px.bar(
        daily, x="d", y="events", color="source_squad",
        color_discrete_map=PALETTE, barmode="stack",
        labels={"d": "Date", "events": "Events", "source_squad": "Squad"},
        title="Events ingested per day, stacked by squad",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#f1f5f9")
    st.plotly_chart(_style(fig, 380), use_container_width=True)

    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.subheader("Status mix per squad")
        status_mix = fdf.groupby(["source_squad", "status"]).size().reset_index(name="n")
        fig = px.bar(
            status_mix, x="source_squad", y="n", color="status",
            barmode="stack",
            labels={"n": "Events", "source_squad": "Squad"},
            title="Outcomes by squad",
        )
        fig.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(_style(fig, 320), use_container_width=True)

    with col_b:
        st.subheader("Volume by payment type")
        pt = fdf.groupby("payment_type").agg(
            events=("event_id", "count"),
            volume_usd=("amount_usd_minor", lambda s: s.sum() / 100.0),
        ).reset_index()
        fig = px.pie(
            pt, names="payment_type", values="volume_usd",
            color="payment_type", color_discrete_map=PT_PALETTE, hole=0.45,
            title="Settled USD volume share",
        )
        fig.update_traces(textinfo="label+percent",
                          texttemplate="<b>%{label}</b><br>%{percent}")
        fig.update_layout(showlegend=False)
        st.plotly_chart(_style(fig, 320), use_container_width=True)

# --- Quarantine ------------------------------------------------------

with tab_quar:
    if fqdf.empty:
        st.success("No quarantined rows in the current filter.")
    else:
        st.subheader(f"Quarantine breakdown ({qrate:.2f}% of input, {quar} rows)")
        col_l, col_r = st.columns([1, 1])

        with col_l:
            counts = fqdf.groupby(["squad", "error_class"]).size().reset_index(name="n")
            fig = px.bar(
                counts.sort_values("n"),
                x="n", y="error_class", color="squad",
                orientation="h", color_discrete_map=PALETTE,
                labels={"n": "Count", "error_class": ""},
                title="Quarantined rows by error class",
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(_style(fig, 360), use_container_width=True)

        with col_r:
            squad_counts = fqdf.groupby("squad").size().reset_index(name="n")
            fig = px.pie(
                squad_counts, names="squad", values="n",
                color="squad", color_discrete_map=PALETTE, hole=0.45,
                title="Quarantine share by squad",
            )
            fig.update_traces(textinfo="label+value+percent")
            fig.update_layout(showlegend=False)
            st.plotly_chart(_style(fig, 360), use_container_width=True)

        st.subheader("Recent quarantined rows")
        st.caption("Each row preserves the original payload and the validation error. Scroll the table or click a header to sort.")
        st.dataframe(
            fqdf[["run_ts", "squad", "error_class", "raw"]].head(50),
            use_container_width=True, hide_index=True,
        )

# --- Schema drift ----------------------------------------------------

with tab_drift:
    st.caption("Distributions of vocabulary fields. New values appearing here are early signals that a squad has shipped a schema change without telling the platform.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Status vocabulary")
        sv = fdf.groupby(["source_squad", "status"]).size().reset_index(name="n")
        fig = px.bar(
            sv, x="status", y="n", color="source_squad",
            color_discrete_map=PALETTE, barmode="stack",
            labels={"n": "Events"},
            title="Status values seen, by squad",
        )
        fig.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(_style(fig, 320), use_container_width=True)

    with col2:
        st.subheader("Event types")
        et = fdf.groupby(["source_squad", "event_type"]).size().reset_index(name="n")
        fig = px.bar(
            et, x="event_type", y="n", color="source_squad",
            color_discrete_map=PALETTE, barmode="stack",
            labels={"n": "Events"},
            title="event_type values, by squad",
        )
        fig.update_yaxes(gridcolor="#f1f5f9")
        fig.update_xaxes(tickangle=-30)
        st.plotly_chart(_style(fig, 320), use_container_width=True)

    with col3:
        st.subheader("Currency mix")
        cm = fdf.groupby(["source_squad", "currency"]).size().reset_index(name="n")
        fig = px.bar(
            cm, x="currency", y="n", color="source_squad",
            color_discrete_map=PALETTE, barmode="stack",
            labels={"n": "Events"},
            title="Currencies seen, by squad",
        )
        fig.update_yaxes(gridcolor="#f1f5f9")
        st.plotly_chart(_style(fig, 320), use_container_width=True)

    st.subheader("FX coverage")
    st.caption("Rows where amount_usd_minor failed to populate (no FX rate for that currency).")
    no_fx = fdf[fdf["amount_usd_minor"].isna()].groupby(["source_squad", "currency"]).size().reset_index(name="rows")
    if no_fx.empty:
        st.success("All rows have a USD-equivalent amount populated.")
    else:
        st.warning(f"{no_fx['rows'].sum()} rows are missing amount_usd_minor.")
        st.dataframe(no_fx, use_container_width=True, hide_index=True)

# --- Lifecycle -------------------------------------------------------

with tab_lifecycle:
    st.caption("Incomplete event chains. These are early signals of stuck transactions, broken capture jobs, or scheduled-but-never-run bills.")

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Cards: auth without capture")
        auths = fdf[(fdf["payment_type"] == "card") & (fdf["event_type"] == "card_auth") & (fdf["status"] == "authorized")]
        captures = fdf[(fdf["payment_type"] == "card") & (fdf["event_type"] == "card_capture")]
        unmatched = auths[~auths["correlation_id"].isin(captures["correlation_id"])]
        st.metric("Open auths (no capture seen)", f"{len(unmatched):,}")
        if len(unmatched):
            st.dataframe(
                unmatched[["customer_id", "counterparty_id", "amount_minor", "currency", "initiated_at"]].head(20),
                use_container_width=True, hide_index=True,
            )

    with col_r:
        st.subheader("Transfers: pending")
        pending_xfer = fdf[(fdf["payment_type"] == "transfer") & (fdf["status"] == "pending")]
        st.metric("Pending transfers in window", f"{len(pending_xfer):,}")
        if len(pending_xfer):
            st.dataframe(
                pending_xfer[["customer_id", "counterparty_id", "amount_minor", "currency", "initiated_at"]].head(20),
                use_container_width=True, hide_index=True,
            )

    st.divider()

    st.subheader("Bills: scheduled but past scheduled date")
    today = datetime.now(timezone.utc).date()
    pending_bills = fdf[(fdf["payment_type"] == "bill_payment") & (fdf["status"] == "pending")]
    pending_bills = pending_bills.assign(scheduled=pending_bills["initiated_at"].dt.date)
    overdue = pending_bills[pending_bills["scheduled"] < today]
    st.metric("Overdue scheduled bills", f"{len(overdue):,}")
    if len(overdue):
        st.dataframe(
            overdue[["customer_id", "counterparty_name", "amount_minor", "currency", "scheduled"]].head(20),
            use_container_width=True, hide_index=True,
        )

# --- Explorer --------------------------------------------------------

with tab_explore:
    st.caption("Sample raw events with their full canonical row. Useful for support, debugging, and ad-hoc investigation.")
    n = st.slider("Rows to show", min_value=10, max_value=200, value=50, step=10)
    show_raw = st.checkbox("Show raw_payload column", value=False)

    cols = [
        "event_timestamp", "source_squad", "event_type", "status", "amount_minor",
        "currency", "amount_usd_minor", "customer_id", "counterparty_id",
        "counterparty_name", "correlation_id",
    ]
    if show_raw:
        cols.append("raw_payload")
    sample = fdf[cols].sort_values("event_timestamp", ascending=False).head(n)
    st.dataframe(sample, use_container_width=True, hide_index=True)
