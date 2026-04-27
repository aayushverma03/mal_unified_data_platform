"""Cards adapter. auth/capture/reversal lifecycle.

correlation_id = hash(txn_id) so paired auth and capture rows share it.
event_type is derived from status and captured_ts. decline_code maps to
a human status_reason.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import AdapterParseError, make_canonical, to_minor

DECLINE_REASON = {"51": "Insufficient funds", "05": "Do not honor", "14": "Invalid card"}


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def to_canonical(row: dict[str, Any], ingested_at: datetime) -> dict[str, Any]:
    raw_status = (row.get("status") or "").upper()
    captured_raw = row.get("captured_ts") or ""
    if raw_status == "APPROVED":
        event_type, status = ("card_capture", "settled") if captured_raw else ("card_auth", "authorized")
    elif raw_status == "DECLINED":
        event_type, status = "card_auth", "failed"
    elif raw_status == "REVERSED":
        event_type, status = "card_reversal", "reversed"
    else:
        raise AdapterParseError(f"unknown cards status: {raw_status!r}")

    decline = (row.get("decline_code") or "").strip()
    merchant = row["merchant_name"]
    return make_canonical(
        source_squad="cards", source_event_id=row["txn_id"],
        idem_discriminator=event_type, payment_type="card", event_type=event_type,
        amount_minor=to_minor(float(row["auth_amount_usd"])),
        currency=row.get("currency_code") or "",
        customer_id=row["customer_ref"], counterparty_type="merchant",
        counterparty_id=merchant.lower().replace(" ", "_"),
        counterparty_name=merchant,
        counterparty_metadata={"mcc": row.get("mcc", "")},
        status=status, status_reason=DECLINE_REASON.get(decline) if decline else None,
        initiated_at=_parse_ts(row["auth_ts"]),
        completed_at=_parse_ts(captured_raw) if captured_raw else None,
        payment_method_details={"card_last4": row.get("card_last4", "")},
        raw_payload=dict(row), ingested_at=ingested_at,
    )
