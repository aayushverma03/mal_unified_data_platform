"""Adapter tests. One happy path and one edge case per squad."""

from datetime import datetime, timezone

import pytest

from mal_payments.adapters import bill_payments, cards, transfers
from mal_payments.adapters.base import AdapterParseError

INGESTED = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)


def test_cards_happy_capture():
    row = {
        "txn_id": "TXN-abc", "card_last4": "1234", "merchant_name": "Carrefour",
        "mcc": "5411", "auth_amount_usd": "100.00",
        "auth_ts": "2026-04-27T11:59:00Z", "captured_ts": "2026-04-27T11:59:30Z",
        "status": "APPROVED", "decline_code": "",
        "customer_ref": "CUST-00001", "currency_code": "AED",
    }
    out = cards.to_canonical(row, INGESTED)
    assert out["event_type"] == "card_capture"
    assert out["status"] == "settled"
    assert out["amount_minor"] == 10000
    assert out["completed_at"] is not None


def test_cards_edge_declined_reason():
    row = {
        "txn_id": "TXN-bad", "card_last4": "1234", "merchant_name": "Talabat",
        "mcc": "5812", "auth_amount_usd": "50.00",
        "auth_ts": "2026-04-27T11:59:00Z", "captured_ts": "",
        "status": "DECLINED", "decline_code": "51",
        "customer_ref": "CUST-00002", "currency_code": "AED",
    }
    out = cards.to_canonical(row, INGESTED)
    assert out["event_type"] == "card_auth"
    assert out["status"] == "failed"
    assert out["status_reason"] == "Insufficient funds"


def test_transfers_happy_amount_parse():
    row = {
        "transfer_uuid": "TR-2026-04-27-0001", "from_account": "AE07-***-1111",
        "to_account": "AE07-***-2222", "amount": "AED 1,250.00",
        "initiated_at": "2026-04-27 12:00:00", "settled_at": "2026-04-27 12:05:00",
        "transfer_type": "P2P", "state": "COMPLETED",
        "customer_id": "CUST-00001", "memo": "Rent",
    }
    out = transfers.to_canonical(row, INGESTED)
    assert out["amount_minor"] == 125000
    assert out["currency"] == "AED"
    assert out["status"] == "settled"


def test_transfers_edge_unparseable_amount():
    row = {
        "transfer_uuid": "TR-2026-04-27-9999", "from_account": "AE07-***-1111",
        "to_account": "AE07-***-2222", "amount": "AED twelve fifty",
        "initiated_at": "2026-04-27 12:00:00", "settled_at": "",
        "transfer_type": "P2P", "state": "PENDING",
        "customer_id": "CUST-00001", "memo": "",
    }
    with pytest.raises(AdapterParseError):
        transfers.to_canonical(row, INGESTED)


def test_bills_happy_paid():
    row = {
        "id": 9001, "biller_code": "DEWA-001", "biller_name": "DEWA",
        "biller_category": "UTILITIES", "amount": "250.00", "currency": "AED",
        "scheduled_for": "2026-04-25", "executed_at": "2026-04-25T08:00:00Z",
        "status": "paid", "customer_id": "CUST-00003",
        "account_at_biller_last4": "1234", "funding_source": "wallet",
    }
    out = bill_payments.to_canonical(row, INGESTED)
    assert out["event_type"] == "bill_paid"
    assert out["status"] == "settled"
    assert out["amount_minor"] == 25000


def test_bills_edge_scheduled_no_executed():
    row = {
        "id": 9002, "biller_code": "DU-020", "biller_name": "du",
        "biller_category": "TELECOM", "amount": "100.00", "currency": "AED",
        "scheduled_for": "2026-05-01", "executed_at": "",
        "status": "scheduled", "customer_id": "CUST-00003",
        "account_at_biller_last4": "5678", "funding_source": "wallet",
    }
    out = bill_payments.to_canonical(row, INGESTED)
    assert out["event_type"] == "bill_scheduled"
    assert out["status"] == "pending"
    assert out["completed_at"] is None
    assert out["initiated_at"].isoformat() == "2026-05-01T00:00:00+00:00"
