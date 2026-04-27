"""Schema migration: canonical v1 to v2.

Reads v1 Parquet, converts via banker's rounding, validates every row
against ``CanonicalPaymentEvent`` v2, writes new Parquet. Idempotent;
source data is never mutated.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl

from ..adapters.base import PIPELINE_VERSION, to_minor
from .canonical_v2 import CanonicalPaymentEvent


def v1_to_v2(row: dict[str, Any], ingested_at: datetime) -> dict[str, Any]:
    """Convert one v1 dict to a v2 canonical dict (pre-validation)."""
    amount_minor = to_minor(Decimal(str(row["amount"])))
    return {
        "event_id": row["event_id"],
        "schema_version": "v2",
        "source_squad": row["source_squad"],
        "source_event_id": row["source_event_id"],
        "correlation_id": row["correlation_id"],
        "idempotency_key": row["idempotency_key"],
        "payment_type": row["payment_type"],
        "event_type": row["event_type"],
        "amount_minor": amount_minor,
        "currency": "USD",
        "amount_usd_minor": amount_minor,
        "fx_rate": Decimal("1.0"),
        "fx_timestamp": ingested_at,
        "customer_id": row["customer_id"],
        "counterparty_type": row["counterparty_type"],
        "counterparty_id": row["counterparty_id"],
        "counterparty_name": row.get("counterparty_name"),
        "counterparty_metadata": json.loads(row.get("counterparty_metadata") or "{}"),
        "status": row["status"],
        "status_reason": row.get("status_reason"),
        "initiated_at": row["initiated_at"],
        "completed_at": row.get("completed_at"),
        "event_timestamp": row["event_timestamp"],
        "payment_method_details": json.loads(row.get("payment_method_details") or "{}"),
        "raw_payload": json.loads(row.get("raw_payload") or "{}"),
        "ingested_at": ingested_at,
        "pipeline_version": PIPELINE_VERSION,
    }


def migrate(v1_dir: Path, v2_path: Path) -> int:
    ingested_at = datetime.now(timezone.utc)
    df = pl.read_parquet(v1_dir / "*.parquet")
    events = [CanonicalPaymentEvent(**v1_to_v2(r, ingested_at)) for r in df.to_dicts()]

    records = []
    for e in events:
        d = e.model_dump()
        d["counterparty_metadata"] = json.dumps(d["counterparty_metadata"], default=str)
        d["payment_method_details"] = json.dumps(d["payment_method_details"], default=str)
        d["raw_payload"] = json.dumps(d["raw_payload"], default=str)
        d["fx_rate"] = float(d["fx_rate"]) if d["fx_rate"] is not None else None
        records.append(d)

    v2_path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(records).write_parquet(v2_path)
    return len(events)
