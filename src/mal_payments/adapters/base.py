"""Adapter contract. Squad row in, canonical dict out.

Adapters MAY raise ``AdapterParseError``; the pipeline quarantines.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Callable

from ulid import ULID

PIPELINE_VERSION = "0.2.0"
FX_TO_USD = {"USD": Decimal("1.0"), "AED": Decimal("0.272"), "GBP": Decimal("1.27")}

Adapter = Callable[[dict[str, Any], datetime], dict[str, Any]]


class AdapterParseError(ValueError):
    """Squad row could not be parsed; route to quarantine."""


def hash16(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def make_event_id(idem: str) -> str:
    return str(ULID.from_bytes(hashlib.sha256(idem.encode()).digest()[:16]))


def to_minor(amount: str | float | Decimal) -> int:
    """Banker's rounding to integer minor units."""
    d = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def usd_minor(amount_minor: int, currency: str) -> tuple[int | None, Decimal | None]:
    rate = FX_TO_USD.get(currency)
    return (int(Decimal(amount_minor) * rate), rate) if rate else (None, None)


def make_canonical(
    *, source_squad: str, source_event_id: str, idem_discriminator: str,
    payment_type: str, event_type: str, amount_minor: int, currency: str,
    customer_id: str, counterparty_type: str, counterparty_id: str,
    status: str, initiated_at: datetime, raw_payload: dict, ingested_at: datetime,
    completed_at: datetime | None = None, counterparty_name: str | None = None,
    counterparty_metadata: dict | None = None, status_reason: str | None = None,
    payment_method_details: dict | None = None,
) -> dict[str, Any]:
    idem = hash16(f"{source_event_id}|{idem_discriminator}")
    usd_amount, fx_rate = usd_minor(amount_minor, currency)
    return {
        "event_id": make_event_id(idem), "schema_version": "v2",
        "source_squad": source_squad, "source_event_id": source_event_id,
        "correlation_id": hash16(source_event_id), "idempotency_key": idem,
        "payment_type": payment_type, "event_type": event_type,
        "amount_minor": amount_minor, "currency": currency,
        "amount_usd_minor": usd_amount, "fx_rate": fx_rate,
        "fx_timestamp": ingested_at if fx_rate is not None else None,
        "customer_id": customer_id, "counterparty_type": counterparty_type,
        "counterparty_id": counterparty_id, "counterparty_name": counterparty_name,
        "counterparty_metadata": counterparty_metadata or {},
        "status": status, "status_reason": status_reason,
        "initiated_at": initiated_at, "completed_at": completed_at,
        "event_timestamp": completed_at or initiated_at,
        "payment_method_details": payment_method_details or {},
        "raw_payload": raw_payload, "ingested_at": ingested_at,
        "pipeline_version": PIPELINE_VERSION,
    }
