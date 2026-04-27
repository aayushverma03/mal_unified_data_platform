"""Mock data generator. Produces the 3 squad CSVs.

Excluded from the 500-line pipeline budget (fixture generator, not
pipeline code). Run via::

    python -m mal_payments.run seed

Faker is seeded with 42; output is byte-identical across runs given a
fixed REFERENCE_DATE.

Spec: ~500 records per squad over a 30-day window, ~2% intentionally
malformed (drives quarantine), ~10% customer overlap across squads,
~15% of cards events form auth->capture pairs sharing a correlation_id.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from faker import Faker

REFERENCE_DATE = datetime(2026, 4, 27, tzinfo=timezone.utc)
SEED = 42

# UAE-realistic merchants (name, MCC)
MERCHANTS = [
    ("Carrefour", "5411"), ("Talabat", "5812"), ("Noon", "5942"),
    ("Amazon AE", "5942"), ("Emirates", "4111"), ("ENOC", "5541"),
    ("Lulu Hypermarket", "5411"), ("Apple Store Dubai Mall", "5732"),
    ("Starbucks", "5814"), ("Costa Coffee", "5814"), ("Sharaf DG", "5732"),
    ("Etisalat", "4814"), ("du", "4814"), ("RTA", "4111"), ("ADNOC", "5541"),
]

# UAE-realistic billers (code, name, category)
BILLERS = [
    ("DEWA-001", "DEWA", "UTILITIES"),
    ("ADWEA-002", "ADWEA", "UTILITIES"),
    ("SEWA-003", "SEWA", "UTILITIES"),
    ("ETI-019", "Etisalat", "TELECOM"),
    ("DU-020", "du", "TELECOM"),
    ("SZHP-007", "Sharjah Police Fines", "GOVERNMENT"),
    ("DLD-008", "Dubai Land Department", "GOVERNMENT"),
    ("RTA-009", "RTA Salik", "GOVERNMENT"),
    ("EI-010", "Emirates ID", "GOVERNMENT"),
    ("TS-011", "Tadweer", "GOVERNMENT"),
    ("DH-012", "Daman Health", "INSURANCE"),
]

CORRIDORS = ["AE", "AE", "AE", "AE", "AE", "AE", "IN", "IN", "PH", "PK", "BD", "EG"]
TRANSFER_TYPES = ["P2P", "ACH", "WIRE", "INSTANT_REMITTANCE"]
FUNDING_SOURCES = ["wallet", "linked_account_AED", "linked_account_USD"]

SHARED_CUST = [f"CUST-{i:05d}" for i in range(1, 11)]
CARDS_CUST = SHARED_CUST + [f"CUST-{i:05d}" for i in range(11, 51)]
TRANSFERS_CUST = SHARED_CUST + [f"CUST-{i:05d}" for i in range(51, 81)]
BILLS_CUST = SHARED_CUST + [f"CUST-{i:05d}" for i in range(81, 101)]


def _setup() -> Faker:
    Faker.seed(SEED)
    random.seed(SEED)
    return Faker()


def _ts(days_ago_max: int = 30) -> datetime:
    secs = random.randint(0, days_ago_max * 86400)
    return REFERENCE_DATE - timedelta(seconds=secs)


def _iso_z(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _gen_cards() -> list[dict]:
    rows: list[dict] = []
    last4_pool = [f"{random.randint(0, 9999):04d}" for _ in range(50)]
    while len(rows) < 490:
        txn_id = f"TXN-{random.randint(0, 16**12 - 1):012x}"
        merchant, mcc = random.choice(MERCHANTS)
        last4 = random.choice(last4_pool)
        amt = round(random.uniform(5.0, 2500.0), 2)
        auth = _ts()
        cust = random.choice(CARDS_CUST)
        currency = random.choices(["AED", "USD", "GBP"], weights=[85, 10, 5])[0]
        status = random.choices(["APPROVED", "DECLINED", "REVERSED"], weights=[85, 10, 5])[0]

        base = {
            "txn_id": txn_id, "card_last4": last4, "merchant_name": merchant,
            "mcc": mcc, "auth_amount_usd": amt, "auth_ts": _iso_z(auth),
            "captured_ts": "", "status": status, "decline_code": "",
            "customer_ref": cust, "currency_code": currency,
        }
        if status == "APPROVED":
            cap_ts = auth + timedelta(seconds=random.randint(1, 60))
            paired = random.random() < 0.08 and len(rows) < 488
            if paired:
                rows.append({**base, "captured_ts": ""})
                rows.append({**base, "captured_ts": _iso_z(cap_ts)})
            else:
                rows.append({**base, "captured_ts": _iso_z(cap_ts)})
        elif status == "DECLINED":
            base["decline_code"] = random.choice(["51", "05", "14"])
            rows.append(base)
        else:  # REVERSED
            cap_ts = auth + timedelta(seconds=random.randint(1, 60))
            rows.append({**base, "captured_ts": _iso_z(cap_ts)})

    # 10 malformed: 4 negative amount, 3 missing currency, 3 short currency
    for i in range(10):
        merchant, mcc = random.choice(MERCHANTS)
        bad: dict = {
            "txn_id": f"TXN-bad{i:09x}", "card_last4": "0000",
            "merchant_name": merchant, "mcc": mcc,
            "auth_amount_usd": round(random.uniform(5.0, 2500.0), 2),
            "auth_ts": _iso_z(_ts()), "captured_ts": _iso_z(_ts()),
            "status": "APPROVED", "decline_code": "",
            "customer_ref": random.choice(CARDS_CUST), "currency_code": "AED",
        }
        if i < 4:
            bad["auth_amount_usd"] = -bad["auth_amount_usd"]
        elif i < 7:
            bad["currency_code"] = ""
        else:
            bad["currency_code"] = "AE"
        rows.append(bad)
    return rows


def _gen_transfers() -> list[dict]:
    rows: list[dict] = []
    for _ in range(490):
        uuid = f"TR-{(REFERENCE_DATE - timedelta(days=random.randint(0,30))).strftime('%Y-%m-%d')}-{random.randint(0,9999):04d}"
        from_acct = f"AE07-***-{random.randint(0,9999):04d}"
        dest = random.choice(CORRIDORS)
        to_acct = f"{dest}{random.randint(0,99):02d}-***-{random.randint(0,9999):04d}"
        currency = "AED"
        amt = random.uniform(50.0, 50000.0)
        amount_str = f"{currency} {amt:,.2f}"
        init = _ts()
        cust = random.choice(TRANSFERS_CUST)
        ttype = random.choice(TRANSFER_TYPES)
        state = random.choices(
            ["COMPLETED", "PENDING", "FAILED", "RETURNED"], weights=[80, 10, 5, 5]
        )[0]
        if state == "COMPLETED":
            settled = (init + timedelta(seconds=random.randint(1, 86400))).strftime("%Y-%m-%d %H:%M:%S")
        else:
            settled = ""
        rows.append({
            "transfer_uuid": uuid, "from_account": from_acct, "to_account": to_acct,
            "amount": amount_str,
            "initiated_at": init.strftime("%Y-%m-%d %H:%M:%S"),
            "settled_at": settled, "transfer_type": ttype, "state": state,
            "customer_id": cust,
            "memo": random.choice(["", "Salary", "Rent", "Family support", "Bills", ""]),
        })

    # 10 malformed: 5 no currency prefix, 5 unparseable
    for i in range(10):
        uuid = f"TR-{REFERENCE_DATE.strftime('%Y-%m-%d')}-bad{i:04d}"
        bad_amount = "1,250.00" if i < 5 else "AED twelve fifty"
        rows.append({
            "transfer_uuid": uuid, "from_account": "AE07-***-0000",
            "to_account": "AE07-***-1111", "amount": bad_amount,
            "initiated_at": _ts().strftime("%Y-%m-%d %H:%M:%S"),
            "settled_at": "", "transfer_type": "P2P", "state": "PENDING",
            "customer_id": random.choice(TRANSFERS_CUST), "memo": "",
        })
    return rows


def _gen_bills() -> list[dict]:
    rows: list[dict] = []
    next_id = 9001
    for _ in range(490):
        code, name, cat = random.choice(BILLERS)
        amt = round(random.uniform(50.0, 5000.0), 2)
        sched = (REFERENCE_DATE - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d")
        status = random.choices(["paid", "scheduled", "failed"], weights=[75, 15, 10])[0]
        executed = _iso_z(_ts()) if status == "paid" else ""
        rows.append({
            "id": next_id, "biller_code": code, "biller_name": name,
            "biller_category": cat, "amount": f"{amt:.2f}", "currency": "AED",
            "scheduled_for": sched, "executed_at": executed, "status": status,
            "customer_id": random.choice(BILLS_CUST),
            "account_at_biller_last4": random.choice(
                [f"{random.randint(0,9999):04d}", "N/A"]
            ),
            "funding_source": random.choice(FUNDING_SOURCES),
        })
        next_id += 1

    # 10 malformed: 5 bad status, 5 bad currency
    for i in range(10):
        code, name, cat = random.choice(BILLERS)
        rows.append({
            "id": next_id + i, "biller_code": code, "biller_name": name,
            "biller_category": cat, "amount": "100.00",
            "currency": "AE" if i >= 5 else "AED",
            "scheduled_for": REFERENCE_DATE.strftime("%Y-%m-%d"),
            "executed_at": "", "status": "paying" if i < 5 else "paid",
            "customer_id": random.choice(BILLS_CUST),
            "account_at_biller_last4": "0000", "funding_source": "wallet",
        })
    return rows


def _write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _gen_v1_parquet(out: Path, n: int = 20) -> None:
    """Synthetic v1 Parquet (float amount in USD) for migration demo."""
    rows = []
    merchants = ["Carrefour", "Talabat", "Noon", "Amazon AE"]
    for i in range(n):
        ts = _ts()
        rows.append({
            "event_id": f"v1-{i:04d}",
            "schema_version": "v1",
            "source_squad": "cards",
            "source_event_id": f"TXN-v1-{i:04d}",
            "correlation_id": f"corr-v1-{i:04d}",
            "idempotency_key": f"idem-v1-{i:04d}",
            "payment_type": "card",
            "event_type": "card_capture",
            "amount": round(random.uniform(5.0, 2500.0), 2),
            "customer_id": random.choice(CARDS_CUST),
            "counterparty_type": "merchant",
            "counterparty_id": random.choice(merchants).lower().replace(" ", "_"),
            "counterparty_name": random.choice(merchants),
            "counterparty_metadata": json.dumps({}),
            "status": "settled",
            "status_reason": None,
            "initiated_at": ts,
            "completed_at": ts,
            "event_timestamp": ts,
            "payment_method_details": json.dumps({}),
            "raw_payload": json.dumps({"v1": True, "ix": i}),
            "ingested_at": ts,
            "pipeline_version": "0.1.0",
        })
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), out)


def seed(root: Path) -> None:
    """Generate all mock fixtures into the project tree."""
    _setup()
    _write_csv(_gen_cards(), root / "data" / "raw" / "cards.csv")
    _write_csv(_gen_transfers(), root / "data" / "raw" / "transfers.csv")
    _write_csv(_gen_bills(), root / "data" / "raw" / "bill_payments.csv")
    _gen_v1_parquet(root / "data" / "output" / "canonical_v1" / "v1_seed.parquet")
