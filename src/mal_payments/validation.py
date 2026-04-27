"""Quarantine-pattern validation. Bad rows do not block good ones."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from .adapters.base import Adapter, AdapterParseError
from .schema.canonical_v2 import CanonicalPaymentEvent


def validate_batch(
    rows: Iterable[dict[str, Any]],
    adapter: Adapter,
    ingested_at: datetime,
) -> tuple[list[CanonicalPaymentEvent], list[dict[str, Any]]]:
    valid: list[CanonicalPaymentEvent] = []
    invalid: list[dict[str, Any]] = []
    for row in rows:
        try:
            event = CanonicalPaymentEvent(**adapter(row, ingested_at))
            valid.append(event)
        except (ValidationError, AdapterParseError) as e:
            invalid.append({"raw": dict(row), "error": str(e)})
    return valid, invalid
