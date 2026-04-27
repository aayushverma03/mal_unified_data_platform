"""Migration tests. v1 to v2."""

from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from mal_payments.schema.migrations import migrate, v1_to_v2

INGESTED = datetime(2026, 4, 27, tzinfo=timezone.utc)


def _v1_row(amount: float, idx: int = 0) -> dict:
    ts = datetime(2026, 4, 26, 10, 0, tzinfo=timezone.utc)
    return {
        "event_id": f"v1-{idx:04d}",
        "schema_version": "v1",
        "source_squad": "cards",
        "source_event_id": f"TXN-{idx:04d}",
        "correlation_id": f"corr-{idx:04d}",
        "idempotency_key": f"idem-{idx:04d}",
        "payment_type": "card",
        "event_type": "card_capture",
        "amount": amount,
        "customer_id": "CUST-00001",
        "counterparty_type": "merchant",
        "counterparty_id": "carrefour",
        "counterparty_name": "Carrefour",
        "counterparty_metadata": "{}",
        "status": "settled",
        "status_reason": None,
        "initiated_at": ts,
        "completed_at": ts,
        "event_timestamp": ts,
        "payment_method_details": "{}",
        "raw_payload": "{}",
        "ingested_at": ts,
        "pipeline_version": "0.1.0",
    }


def test_amount_no_float_drift():
    out = v1_to_v2(_v1_row(12.34), INGESTED)
    assert out["amount_minor"] == 1234
    assert out["amount_usd_minor"] == 1234
    assert out["currency"] == "USD"
    assert out["schema_version"] == "v2"


@pytest.mark.parametrize("amount,expected", [
    (12.34, 1234),
    (12.345, 1234),  # ROUND_HALF_EVEN: .5 with even predecessor rounds down
    (12.355, 1236),  # .5 with odd predecessor rounds up
    (0.005, 0),      # 0.005 -> 0 (banker's rounds to even 0)
    (0.015, 2),      # 0.015 -> 2 (banker's rounds to even 2)
    (1000.00, 100000),
])
def test_bankers_rounding_boundary(amount, expected):
    out = v1_to_v2(_v1_row(amount), INGESTED)
    assert out["amount_minor"] == expected


def test_migrate_round_trip(tmp_path: Path):
    rows = [_v1_row(round(i * 1.23, 2), i) for i in range(100)]
    v1_dir = tmp_path / "v1"
    v1_dir.mkdir()
    pq.write_table(pa.Table.from_pylist(rows), v1_dir / "seed.parquet")

    v2_path = tmp_path / "v2.parquet"
    n = migrate(v1_dir, v2_path)
    assert n == 100

    df = pl.read_parquet(v2_path)
    assert df.shape[0] == 100
    assert (df["schema_version"] == "v2").all()
    # Sum check: v2 amount_minor must equal int(amount*100) for each row
    expected_total = sum(int(round(r["amount"] * 100)) for r in rows)
    assert df["amount_minor"].sum() == expected_total
