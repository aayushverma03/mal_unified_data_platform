"""Transfers adapter. wire, P2P, and remittance.

Amount strings like ``"AED 1,250.00"`` are regex-parsed; unparseable
values raise ``AdapterParseError``. Naive timestamps are assumed
Asia/Dubai and converted to UTC.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from .base import AdapterParseError, make_canonical, to_minor

DUBAI = ZoneInfo("Asia/Dubai")
UTC = ZoneInfo("UTC")
_AMOUNT_RE = re.compile(r"^([A-Z]{3})\s+([\d,]+(?:\.\d+)?)$")
STATE_TO_STATUS = {"COMPLETED": "settled", "PENDING": "pending", "FAILED": "failed", "RETURNED": "reversed"}
STATE_TO_EVENT = {"COMPLETED": "transfer_settled", "PENDING": "transfer_initiated", "FAILED": "transfer_failed", "RETURNED": "transfer_returned"}


def _parse_amount(s: str) -> tuple[int, str]:
    m = _AMOUNT_RE.match(s.strip())
    if not m:
        raise AdapterParseError(f"unparseable transfers amount: {s!r}")
    return to_minor(Decimal(m.group(2).replace(",", ""))), m.group(1)


def _to_utc(naive_str: str) -> datetime:
    return datetime.strptime(naive_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=DUBAI).astimezone(UTC)


def to_canonical(row: dict[str, Any], ingested_at: datetime) -> dict[str, Any]:
    state = (row.get("state") or "").upper()
    if state not in STATE_TO_STATUS:
        raise AdapterParseError(f"unknown transfers state: {state!r}")
    amount_minor, currency = _parse_amount(row["amount"])
    settled_raw = row.get("settled_at") or ""
    return make_canonical(
        source_squad="transfers", source_event_id=row["transfer_uuid"],
        idem_discriminator=state, payment_type="transfer",
        event_type=STATE_TO_EVENT[state], amount_minor=amount_minor, currency=currency,
        customer_id=row["customer_id"], counterparty_type="account",
        counterparty_id=row["to_account"], status=STATE_TO_STATUS[state],
        initiated_at=_to_utc(row["initiated_at"]),
        completed_at=_to_utc(settled_raw) if settled_raw else None,
        payment_method_details={
            "transfer_type": row.get("transfer_type", ""),
            "from_account": row.get("from_account", ""),
            "memo": row.get("memo", ""),
        },
        raw_payload=dict(row), ingested_at=ingested_at,
    )
