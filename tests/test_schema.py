"""Tests for the canonical schema (v2)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from mal_payments.schema.canonical_v2 import CanonicalPaymentEvent


def _valid() -> dict:
    now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    return {
        "event_id": "01HXY...",
        "source_squad": "cards",
        "source_event_id": "TXN-abc",
        "correlation_id": "corr-1",
        "idempotency_key": "idem-1",
        "payment_type": "card",
        "event_type": "card_capture",
        "amount_minor": 12345,
        "currency": "AED",
        "customer_id": "CUST-00001",
        "counterparty_type": "merchant",
        "counterparty_id": "carrefour",
        "status": "settled",
        "initiated_at": now,
        "event_timestamp": now,
        "raw_payload": {"x": 1},
        "ingested_at": now,
        "pipeline_version": "0.2.0",
    }


def test_valid_event_constructs():
    e = CanonicalPaymentEvent(**_valid())
    assert e.amount_minor == 12345
    assert e.schema_version == "v2"


def test_missing_required_field_raises():
    d = _valid()
    del d["amount_minor"]
    with pytest.raises(ValidationError):
        CanonicalPaymentEvent(**d)


def test_bad_currency_length_raises():
    for bad in ("AE", "AEDX", ""):
        d = _valid() | {"currency": bad}
        with pytest.raises(ValidationError):
            CanonicalPaymentEvent(**d)


def test_negative_amount_raises():
    d = _valid() | {"amount_minor": -1}
    with pytest.raises(ValidationError):
        CanonicalPaymentEvent(**d)


def test_extra_field_forbidden():
    d = _valid() | {"unknown_field": "boom"}
    with pytest.raises(ValidationError):
        CanonicalPaymentEvent(**d)


def test_frozen_immutable():
    e = CanonicalPaymentEvent(**_valid())
    with pytest.raises(ValidationError):
        e.amount_minor = 999
