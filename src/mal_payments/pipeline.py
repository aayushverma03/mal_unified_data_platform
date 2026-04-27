"""Pipeline: ingest, adapt, validate, write.

Single-process. Production would use Dagster (D2). Canonical output is
idempotent because event_id is a deterministic ULID from idempotency_key.
Quarantine paths are timestamped per run.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

from .adapters import bill_payments, cards, transfers
from .adapters.base import Adapter
from .schema.canonical_v2 import CanonicalPaymentEvent
from .validation import validate_batch

log = logging.getLogger("mal_payments.pipeline")

ADAPTERS: dict[str, tuple[Adapter, str]] = {
    "cards": (cards.to_canonical, "cards.csv"),
    "transfers": (transfers.to_canonical, "transfers.csv"),
    "bill_payments": (bill_payments.to_canonical, "bill_payments.csv"),
}


def _to_record(event: CanonicalPaymentEvent) -> dict[str, Any]:
    d = event.model_dump()
    d["counterparty_metadata"] = json.dumps(d["counterparty_metadata"], default=str)
    d["payment_method_details"] = json.dumps(d["payment_method_details"], default=str)
    d["raw_payload"] = json.dumps(d["raw_payload"], default=str)
    if d.get("fx_rate") is not None:
        d["fx_rate"] = float(d["fx_rate"])
    d["event_date"] = d["event_timestamp"].date().isoformat()
    return d


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    df = pl.read_csv(path, infer_schema_length=0)
    return df.to_dicts()


def _write_quarantine(invalid: list[dict[str, Any]], squad: str, run_dir: Path) -> None:
    if not invalid:
        return
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / f"{squad}.json").open("w") as f:
        json.dump(invalid, f, indent=2, default=str)


def ingest(root: Path) -> None:
    ingested_at = datetime.now(timezone.utc)
    canonical_out = root / "data" / "output" / "canonical"
    quarantine_run = (
        root / "data" / "output" / "quarantine"
        / ingested_at.strftime("%Y-%m-%dT%H-%M-%SZ")
    )

    all_records: list[dict[str, Any]] = []
    for squad, (adapter, csv_name) in ADAPTERS.items():
        rows = _read_csv_rows(root / "data" / "raw" / csv_name)
        valid, invalid = validate_batch(rows, adapter, ingested_at)
        all_records.extend(_to_record(e) for e in valid)
        _write_quarantine(invalid, squad, quarantine_run)
        log.info("%s: valid=%d quarantine=%d", squad, len(valid), len(invalid))

    if canonical_out.exists():
        shutil.rmtree(canonical_out)
    canonical_out.mkdir(parents=True)
    pl.DataFrame(all_records).write_parquet(
        canonical_out, partition_by=["event_date", "payment_type"]
    )
