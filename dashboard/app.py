"""Mal Payments Data Quality Dashboard. Streamlit app for D3.

Run locally:  uv run streamlit run dashboard/app.py
Cloud deploy: see dashboard/README.md.

Reads:
  - data/output/canonical/  (canonical Parquet, partitioned)
  - data/output/quarantine/ (per-run JSON files with bad rows)

If outputs are missing on cold start (Streamlit Cloud), the app
auto-runs `seed` and `ingest` so the dashboard is never empty.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import polars as pl
import streamlit as st

HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data"
CANONICAL = DATA / "output" / "canonical"
QUARANTINE = DATA / "output" / "quarantine"

PALETTE = {"cards": "#ef4444", "transfers": "#2563eb", "bill_payments": "#10b981"}
PT_PALETTE = {"card": "#ef4444", "transfer": "#2563eb", "bill_payment": "#10b981"}
STATUS_PALETTE = {
    "settled": "#10b981", "authorized": "#3b82f6", "pending": "#f59e0b",
    "failed": "#ef4444", "reversed": "#a855f7", "refunded": "#ec4899",
    "initiated": "#94a3b8",
}

# Health thresholds.
QUAR_TARGET_PCT = 2.0
QUAR_WARN_PCT = 5.0
OVERDUE_WARN = 30


# --- Data loading ----------------------------------------------------

def _ensure_data() -> None:
    if any(CANONICAL.glob("**/*.parquet")):
        return
    from mal_payments.mock_data import seed
    from mal_payments.pipeline import ingest
    seed(ROOT)
    ingest(ROOT)


@st.cache_data(ttl=300)
def load_canonical() -> pd.DataFrame:
    _ensure_data()
    df = pl.read_parquet(str(CANONICAL / "**" / "*.parquet")).to_pandas()
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"])
    df["initiated_at"] = pd.to_datetime(df["initiated_at"])
    return df


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
                        "run_ts": run_ts, "squad": squad,
                        "error_class": err_class, "error": entry["error"],
                        "raw_preview": json.dumps(entry["raw"], default=str)[:180],
                    })
    return pd.DataFrame(rows)


def _style(fig, height=360):
    fig.update_layout(
        template="plotly_white", height=height,
        margin=dict(l=10, r=10, t=20, b=10),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color="#334155"),
        title=None,
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.22,
            xanchor="left", x=0, title_text="",
            bgcolor="rgba(255,255,255,0)", borderwidth=0,
        ),
    )
    fig.update_xaxes(showgrid=False, linecolor="#e5e7eb", zeroline=False, title=None)
    fig.update_yaxes(gridcolor="#f1f5f9", linecolor="#e5e7eb", zeroline=False)
    return fig


# --- Page setup ------------------------------------------------------

st.set_page_config(
    page_title="Mal Payments | Data Quality",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {padding-top: 1.25rem; padding-bottom: 3rem; max-width: 1400px;}
section[data-testid="stSidebar"] {background-color: #f8fafc;}
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {color: #0f172a; font-weight: 600;}
[data-testid="stMetricLabel"] p {font-size: 0.78rem; color: #64748b; font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em;}
[data-testid="stMetricValue"] {font-size: 1.85rem; font-weight: 700; color: #0f172a; line-height: 1.1;}
[data-testid="stMetricDelta"] {font-size: 0.85rem; font-weight: 500;}
h1 {font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; color: #0f172a; margin-bottom: 0.25rem;}
h2 {font-size: 1.1rem; font-weight: 600; letter-spacing: -0.01em; color: #0f172a; margin-top: 1.5rem; margin-bottom: 0.75rem;}
h3 {font-size: 0.95rem; font-weight: 600; color: #334155;}
hr {margin: 1rem 0; border-color: #e5e7eb;}
.stTabs [data-baseweb="tab-list"] {gap: 0.5rem; border-bottom: 1px solid #e5e7eb;}
.stTabs [data-baseweb="tab"] {padding: 0.5rem 0.75rem; font-weight: 500; color: #475569;}
.stTabs [aria-selected="true"] {color: #0f172a; font-weight: 600;}
.health-pill {display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.45rem 0.9rem; border-radius: 999px; font-weight: 600; font-size: 0.9rem;}
.health-ok {background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0;}
.health-warn {background: #fffbeb; color: #92400e; border: 1px solid #fcd34d;}
.health-crit {background: #fef2f2; color: #991b1b; border: 1px solid #fca5a5;}
.dot {width: 8px; height: 8px; border-radius: 50%; display: inline-block;}
.dot-ok {background: #10b981;} .dot-warn {background: #f59e0b;} .dot-crit {background: #ef4444;}
[data-testid="stDataFrame"] {border-radius: 8px; border: 1px solid #e5e7eb;}
</style>
""", unsafe_allow_html=True)

# --- Header ----------------------------------------------------------

col_title, col_refresh = st.columns([5, 1])
with col_title:
    st.markdown("# Data quality")
    st.caption("Platform reliability view across Cards, Transfers, and Bill Payments. Real-time signals on ingestion volume, validation failures, schema drift, and stuck transactions.")
with col_refresh:
    st.write("")
    if st.button("Reload data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with st.spinner("Loading canonical event store..."):
    df_all = load_canonical()
    qdf_all = load_quarantine()

# --- Sidebar filters -------------------------------------------------

with st.sidebar:
    st.header("Filters")
    min_d = df_all["event_timestamp"].min().date()
    max_d = df_all["event_timestamp"].max().date()
    date_range = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range
    else:
        start_d, end_d = min_d, max_d

    squads = st.multiselect(
        "Source squad",
        options=sorted(df_all["source_squad"].unique()),
        default=sorted(df_all["source_squad"].unique()),
    )
    statuses = st.multiselect(
        "Status",
        options=sorted(df_all["status"].unique()),
        default=sorted(df_all["status"].unique()),
    )

    st.markdown("---")
    st.caption("**Pipeline** mal_payments v0.2.0")
    st.caption(f"**Window** {min_d} to {max_d}")
    st.caption(f"**Source** canonical Parquet ({len(df_all):,} rows)")

mask = (
    (df_all["event_timestamp"].dt.date >= start_d)
    & (df_all["event_timestamp"].dt.date <= end_d)
    & (df_all["source_squad"].isin(squads))
    & (df_all["status"].isin(statuses))
)
df = df_all.loc[mask].copy()
qdf = qdf_all[qdf_all["squad"].isin(squads)] if not qdf_all.empty and squads else qdf_all

# --- Health computation ----------------------------------------------

total = len(df)
settled = (df["status"] == "settled").sum()
quar = len(qdf)
input_total = total + quar
qrate = (quar / input_total * 100) if input_total else 0.0

today = datetime.now(timezone.utc).date()
overdue_bills = df[
    (df["payment_type"] == "bill_payment")
    & (df["status"] == "pending")
    & (df["initiated_at"].dt.date < today)
].shape[0]
pending_xfer = df[(df["payment_type"] == "transfer") & (df["status"] == "pending")].shape[0]

issues = []
if qrate >= QUAR_WARN_PCT:
    issues.append(("crit", f"Quarantine rate {qrate:.2f}% above {QUAR_WARN_PCT}% threshold"))
elif qrate >= QUAR_TARGET_PCT:
    issues.append(("warn", f"Quarantine rate {qrate:.2f}% above {QUAR_TARGET_PCT}% target"))
if overdue_bills > OVERDUE_WARN:
    issues.append(("warn", f"{overdue_bills} bills scheduled but not executed"))

if not issues:
    pill_class, pill_text = "health-ok", f"All systems healthy. {total:,} events ingested, {qrate:.2f}% quarantine rate (target <{QUAR_TARGET_PCT}%)."
    dot_class = "dot-ok"
elif any(sev == "crit" for sev, _ in issues):
    pill_class = "health-crit"; dot_class = "dot-crit"
    pill_text = "Action required. " + "; ".join(msg for _, msg in issues)
else:
    pill_class = "health-warn"; dot_class = "dot-warn"
    pill_text = "Attention. " + "; ".join(msg for _, msg in issues)

st.markdown(
    f'<div class="health-pill {pill_class}"><span class="dot {dot_class}"></span>{pill_text}</div>',
    unsafe_allow_html=True,
)

st.write("")

# --- KPI tiles -------------------------------------------------------

settled_usd = df.loc[df["status"] == "settled", "amount_usd_minor"].sum() / 100.0
distinct = df["customer_id"].nunique()
last_seen = df["event_timestamp"].max() if total else None
hrs_since = (datetime.now(timezone.utc) - last_seen.tz_convert("UTC")).total_seconds() / 3600 if last_seen is not None else None

# Last 7d vs prior period (within selected range), to give meaningful deltas.
window_end = pd.Timestamp(end_d).tz_localize("UTC")
last7_start = window_end - pd.Timedelta(days=7)
prior_start = last7_start - pd.Timedelta(days=7)
last7 = df[(df["event_timestamp"] >= last7_start) & (df["event_timestamp"] <= window_end)]
prior = df[(df["event_timestamp"] >= prior_start) & (df["event_timestamp"] < last7_start)]
events_last7 = len(last7); events_prior = len(prior)
events_delta = (events_last7 - events_prior) / events_prior * 100 if events_prior else 0.0
volume_last7 = last7.loc[last7["status"] == "settled", "amount_usd_minor"].sum() / 100.0
volume_prior = prior.loc[prior["status"] == "settled", "amount_usd_minor"].sum() / 100.0
volume_delta = (volume_last7 - volume_prior) / volume_prior * 100 if volume_prior else 0.0

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    with st.container(border=True):
        st.metric("Canonical events", f"{total:,}",
                  delta=f"{events_delta:+.1f}% last 7d" if events_prior else None)
with k2:
    with st.container(border=True):
        st.metric("Settled volume", f"${settled_usd:,.0f}",
                  delta=f"{volume_delta:+.1f}% last 7d" if volume_prior else None)
with k3:
    with st.container(border=True):
        delta_q = f"target <{QUAR_TARGET_PCT}%"
        st.metric("Quarantine rate", f"{qrate:.2f}%", delta=delta_q,
                  delta_color="inverse" if qrate > QUAR_TARGET_PCT else "off")
with k4:
    with st.container(border=True):
        st.metric("Distinct customers", f"{distinct:,}",
                  delta=f"{len(squads)} squads", delta_color="off")
with k5:
    with st.container(border=True):
        last_str = last_seen.strftime("%Y-%m-%d %H:%M") if last_seen is not None else "no data"
        delta_age = f"{hrs_since:.0f}h ago" if hrs_since else None
        st.metric("Latest event", last_str, delta=delta_age, delta_color="off")

st.write("")

# --- Tabs ------------------------------------------------------------

tab_overview, tab_quar, tab_drift, tab_lifecycle, tab_explore = st.tabs(
    ["Overview", "Quarantine", "Schema drift", "Lifecycle", "Explorer"]
)

# --- Overview --------------------------------------------------------

with tab_overview:
    st.markdown("## Daily ingestion")
    daily = (
        df.assign(d=df["event_timestamp"].dt.date)
        .groupby(["d", "source_squad"]).size().reset_index(name="events")
    )
    fig = px.bar(
        daily, x="d", y="events", color="source_squad",
        color_discrete_map=PALETTE, barmode="stack",
        labels={"d": "", "events": "Events", "source_squad": "Squad"},
    )
    fig.update_traces(hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y} events<extra></extra>")
    st.plotly_chart(_style(fig, 360), use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("## Outcomes by squad")
        status_mix = df.groupby(["source_squad", "status"]).size().reset_index(name="n")
        fig = px.bar(
            status_mix, y="source_squad", x="n", color="status",
            barmode="stack", orientation="h",
            color_discrete_map=STATUS_PALETTE,
            labels={"n": "Events", "source_squad": "", "status": "Status"},
        )
        fig.update_traces(hovertemplate="<b>%{y}</b> | %{fullData.name}: %{x}<extra></extra>")
        st.plotly_chart(_style(fig, 320), use_container_width=True)

    with col_b:
        st.markdown("## Settled USD by payment type")
        pt = df[df["status"] == "settled"].groupby("payment_type").agg(
            volume_usd=("amount_usd_minor", lambda s: s.sum() / 100.0),
        ).reset_index()
        fig = px.pie(
            pt, names="payment_type", values="volume_usd",
            color="payment_type", color_discrete_map=PT_PALETTE, hole=0.55,
        )
        fig.update_traces(
            textinfo="label+percent",
            texttemplate="<b>%{label}</b><br>%{percent}",
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<extra></extra>",
            marker=dict(line=dict(color="white", width=2)),
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(_style(fig, 320), use_container_width=True)

# --- Quarantine ------------------------------------------------------

with tab_quar:
    if qdf.empty:
        st.success("No quarantined rows in the current filter.")
    else:
        m1, m2, m3 = st.columns(3)
        with m1:
            with st.container(border=True):
                st.metric("Rows quarantined", f"{quar:,}")
        with m2:
            with st.container(border=True):
                st.metric("Quarantine rate", f"{qrate:.2f}%",
                          delta=f"target <{QUAR_TARGET_PCT}%",
                          delta_color="inverse" if qrate > QUAR_TARGET_PCT else "off")
        with m3:
            with st.container(border=True):
                st.metric("Distinct error classes", f"{qdf['error_class'].nunique()}")

        st.write("")

        col_l, col_r = st.columns([3, 2])
        with col_l:
            st.markdown("## Quarantine by error class")
            counts = qdf.groupby(["squad", "error_class"]).size().reset_index(name="n")
            fig = px.bar(
                counts.sort_values("n"), x="n", y="error_class", color="squad",
                orientation="h", color_discrete_map=PALETTE,
                labels={"n": "Rows", "error_class": "", "squad": "Squad"},
            )
            fig.update_traces(hovertemplate="<b>%{y}</b><br>%{fullData.name}: %{x}<extra></extra>")
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(_style(fig, 360), use_container_width=True)

        with col_r:
            st.markdown("## Share by squad")
            squad_counts = qdf.groupby("squad").size().reset_index(name="n")
            fig = px.pie(
                squad_counts, names="squad", values="n",
                color="squad", color_discrete_map=PALETTE, hole=0.55,
            )
            fig.update_traces(
                textinfo="label+value",
                texttemplate="<b>%{label}</b><br>%{value}",
                hovertemplate="<b>%{label}</b><br>%{value} rows (%{percent})<extra></extra>",
                marker=dict(line=dict(color="white", width=2)),
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(_style(fig, 360), use_container_width=True)

        st.markdown("## Recent quarantined rows")
        st.caption("Each row preserves the original payload and the validation error. Click a column header to sort.")
        st.dataframe(
            qdf[["run_ts", "squad", "error_class", "raw_preview"]].head(50),
            use_container_width=True, hide_index=True,
            column_config={
                "run_ts": st.column_config.TextColumn("Run", width="small"),
                "squad": st.column_config.TextColumn("Squad", width="small"),
                "error_class": st.column_config.TextColumn("Error class", width="medium"),
                "raw_preview": st.column_config.TextColumn("Original payload (preview)", width="large"),
            },
        )

# --- Schema drift ----------------------------------------------------

with tab_drift:
    st.caption("Distributions of vocabulary fields. New values appearing here are early signals that a squad shipped a schema change without telling the platform.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("## Status vocabulary")
        sv = df.groupby(["source_squad", "status"]).size().reset_index(name="n")
        fig = px.bar(
            sv, x="status", y="n", color="source_squad",
            color_discrete_map=PALETTE, barmode="stack",
            labels={"n": "Events", "status": "", "source_squad": "Squad"},
        )
        fig.update_traces(hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y}<extra></extra>")
        st.plotly_chart(_style(fig, 320), use_container_width=True)

    with col2:
        st.markdown("## Currency mix")
        cm = df.groupby(["source_squad", "currency"]).size().reset_index(name="n")
        fig = px.bar(
            cm, x="currency", y="n", color="source_squad",
            color_discrete_map=PALETTE, barmode="stack",
            labels={"n": "Events", "currency": "", "source_squad": "Squad"},
        )
        fig.update_traces(hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y}<extra></extra>")
        st.plotly_chart(_style(fig, 320), use_container_width=True)

    st.markdown("## event_type vocabulary")
    et = df.groupby(["source_squad", "event_type"]).size().reset_index(name="n")
    fig = px.bar(
        et, x="event_type", y="n", color="source_squad",
        color_discrete_map=PALETTE, barmode="stack",
        labels={"n": "Events", "event_type": "", "source_squad": "Squad"},
    )
    fig.update_traces(hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y}<extra></extra>")
    fig.update_xaxes(tickangle=-25)
    st.plotly_chart(_style(fig, 340), use_container_width=True)

    st.markdown("## FX coverage")
    no_fx = df[df["amount_usd_minor"].isna()].groupby(["source_squad", "currency"]).size().reset_index(name="rows")
    if no_fx.empty:
        st.success("All rows have a USD-equivalent amount populated.")
    else:
        st.warning(f"{no_fx['rows'].sum()} rows are missing amount_usd_minor.")
        st.dataframe(no_fx, use_container_width=True, hide_index=True)

# --- Lifecycle -------------------------------------------------------

with tab_lifecycle:
    st.caption("Incomplete event chains. Early signals of stuck transactions, broken capture jobs, or scheduled bills that never executed.")

    auths = df[(df["payment_type"] == "card") & (df["event_type"] == "card_auth") & (df["status"] == "authorized")]
    captures = df[(df["payment_type"] == "card") & (df["event_type"] == "card_capture")]
    unmatched = auths[~auths["correlation_id"].isin(captures["correlation_id"])]

    pending_xfer_df = df[(df["payment_type"] == "transfer") & (df["status"] == "pending")]
    pending_bills = df[(df["payment_type"] == "bill_payment") & (df["status"] == "pending")].copy()
    pending_bills["scheduled"] = pending_bills["initiated_at"].dt.date
    overdue = pending_bills[pending_bills["scheduled"] < today]

    m1, m2, m3 = st.columns(3)
    with m1:
        with st.container(border=True):
            st.metric("Open auths (no capture)", f"{len(unmatched):,}",
                      delta="cards" if len(unmatched) else None, delta_color="off")
    with m2:
        with st.container(border=True):
            st.metric("Pending transfers", f"{len(pending_xfer_df):,}",
                      delta="transfers" if len(pending_xfer_df) else None, delta_color="off")
    with m3:
        with st.container(border=True):
            st.metric("Overdue scheduled bills", f"{len(overdue):,}",
                      delta="past scheduled date" if len(overdue) else None,
                      delta_color="inverse" if len(overdue) > OVERDUE_WARN else "off")

    st.write("")

    if len(unmatched):
        st.markdown("## Cards: authorized but not captured")
        st.dataframe(
            unmatched[["initiated_at", "customer_id", "counterparty_name", "amount_minor", "currency", "correlation_id"]]
                .sort_values("initiated_at", ascending=False).head(20),
            use_container_width=True, hide_index=True,
        )

    if len(pending_xfer_df):
        st.markdown("## Transfers: pending settlement")
        st.dataframe(
            pending_xfer_df[["initiated_at", "customer_id", "counterparty_id", "amount_minor", "currency"]]
                .sort_values("initiated_at", ascending=False).head(20),
            use_container_width=True, hide_index=True,
        )

    if len(overdue):
        st.markdown("## Bills: scheduled date passed, not yet executed")
        st.dataframe(
            overdue[["scheduled", "customer_id", "counterparty_name", "amount_minor", "currency"]]
                .sort_values("scheduled", ascending=True).head(20),
            use_container_width=True, hide_index=True,
        )

# --- Explorer --------------------------------------------------------

with tab_explore:
    st.caption("Sample recent events with their full canonical row. Useful for support, debugging, and ad-hoc investigation.")
    col_n, col_raw = st.columns([1, 4])
    with col_n:
        n = st.number_input("Rows", min_value=10, max_value=500, value=50, step=10)
    with col_raw:
        st.write("")
        show_raw = st.checkbox("Include raw_payload column", value=False)

    cols = [
        "event_timestamp", "source_squad", "event_type", "status",
        "amount_minor", "currency", "amount_usd_minor",
        "customer_id", "counterparty_id", "counterparty_name", "correlation_id",
    ]
    if show_raw:
        cols.append("raw_payload")
    sample = df[cols].sort_values("event_timestamp", ascending=False).head(int(n))
    st.dataframe(sample, use_container_width=True, hide_index=True)
