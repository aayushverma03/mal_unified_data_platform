"""Bill Payments adapter. Biller payments.

scheduled_for is date-only, so initiated_at = scheduled_for at 00:00 UTC.
biller_category is preserved in counterparty_metadata for downstream
halal-spending classification.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal
from typing import Any

from .base import AdapterParseError, make_canonical, to_minor

STATUS_MAP = {"paid": "settled", "scheduled": "pending", "failed": "failed"}
EVENT_MAP = {"paid": "bill_paid", "scheduled": "bill_scheduled", "failed": "bill_failed"}


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def to_canonical(row: dict[str, Any], ingested_at: datetime) -> dict[str, Any]:
    raw_status = (row.get("status") or "").lower()
    if raw_status not in STATUS_MAP:
        raise AdapterParseError(f"unknown bill_payments status: {raw_status!r}")

    sched = datetime.strptime(row["scheduled_for"], "%Y-%m-%d").date()
    executed_raw = row.get("executed_at") or ""
    return make_canonical(
        source_squad="bill_payments", source_event_id=str(row["id"]),
        idem_discriminator=raw_status, payment_type="bill_payment",
        event_type=EVENT_MAP[raw_status],
        amount_minor=to_minor(Decimal(row["amount"])),
        currency=row.get("currency") or "",
        customer_id=row["customer_id"], counterparty_type="biller",
        counterparty_id=row["biller_code"], counterparty_name=row.get("biller_name"),
        counterparty_metadata={"biller_category": row.get("biller_category", "")},
        status=STATUS_MAP[raw_status],
        initiated_at=datetime.combine(sched, time.min, tzinfo=timezone.utc),
        completed_at=_parse_ts(executed_raw) if executed_raw else None,
        payment_method_details={
            "funding_source": row.get("funding_source", ""),
            "account_at_biller_last4": row.get("account_at_biller_last4", ""),
        },
        raw_payload=dict(row), ingested_at=ingested_at,
    )
