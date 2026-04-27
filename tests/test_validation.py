"""Validation tests. Quarantine routing."""

from datetime import datetime, timezone

from mal_payments.adapters import cards, transfers
from mal_payments.schema.canonical_v2 import CanonicalPaymentEvent
from mal_payments.validation import validate_batch

INGESTED = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)


def _good_card_row(txn: str = "TXN-1") -> dict:
    return {
        "txn_id": txn, "card_last4": "1234", "merchant_name": "Carrefour",
        "mcc": "5411", "auth_amount_usd": "100.00",
        "auth_ts": "2026-04-27T11:59:00Z", "captured_ts": "2026-04-27T11:59:30Z",
        "status": "APPROVED", "decline_code": "",
        "customer_ref": "CUST-00001", "currency_code": "AED",
    }


def test_valid_row_returns_event():
    valid, invalid = validate_batch([_good_card_row()], cards.to_canonical, INGESTED)
    assert len(valid) == 1 and len(invalid) == 0
    assert isinstance(valid[0], CanonicalPaymentEvent)


def test_validation_error_quarantines():
    bad = _good_card_row() | {"auth_amount_usd": "-5.00"}  # negative -> Pydantic ge=0 fails
    valid, invalid = validate_batch([bad], cards.to_canonical, INGESTED)
    assert valid == []
    assert len(invalid) == 1
    assert "raw" in invalid[0] and "error" in invalid[0]


def test_adapter_parse_error_quarantines():
    bad_transfer = {
        "transfer_uuid": "TR-x", "from_account": "AE07-***-1111",
        "to_account": "AE07-***-2222", "amount": "AED twelve fifty",
        "initiated_at": "2026-04-27 12:00:00", "settled_at": "",
        "transfer_type": "P2P", "state": "PENDING",
        "customer_id": "CUST-1", "memo": "",
    }
    valid, invalid = validate_batch([bad_transfer], transfers.to_canonical, INGESTED)
    assert valid == []
    assert len(invalid) == 1


def test_mixed_batch_counts_preserved():
    rows = [_good_card_row("TXN-1"), _good_card_row("TXN-2") | {"currency_code": ""}, _good_card_row("TXN-3")]
    valid, invalid = validate_batch(rows, cards.to_canonical, INGESTED)
    assert len(valid) == 2 and len(invalid) == 1
