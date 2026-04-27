"""CLI entry point. ``python -m mal_payments.run <command>``.

Subcommands: seed, ingest, migrate, validate. Uses argparse (stdlib).
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import polars as pl

from .mock_data import seed
from .pipeline import ingest
from .schema.canonical_v2 import CanonicalPaymentEvent
from .schema.migrations import migrate

ROOT = Path(__file__).resolve().parents[2]


def _validate(root: Path) -> None:
    df = pl.read_parquet(root / "data" / "output" / "canonical" / "**/*.parquet")
    valid = invalid = 0
    for row in df.to_dicts():
        row.pop("event_date", None)
        try:
            row["counterparty_metadata"] = json.loads(row["counterparty_metadata"])
            row["payment_method_details"] = json.loads(row["payment_method_details"])
            row["raw_payload"] = json.loads(row["raw_payload"])
            CanonicalPaymentEvent(**row)
            valid += 1
        except Exception:
            invalid += 1
    logging.info("validate: valid=%d invalid=%d", valid, invalid)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="mal_payments.run")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed", help="regenerate the 3 mock CSVs + v1 parquet")
    sub.add_parser("ingest", help="CSV -> canonical Parquet")
    sub.add_parser("migrate", help="v1 -> v2 schema migration demo")
    sub.add_parser("validate", help="re-validate canonical Parquet against current schema")
    args = parser.parse_args()

    if args.cmd == "seed":
        seed(ROOT)
    elif args.cmd == "ingest":
        ingest(ROOT)
    elif args.cmd == "migrate":
        n = migrate(
            ROOT / "data" / "output" / "canonical_v1",
            ROOT / "data" / "output" / "canonical_v2" / "migrated.parquet",
        )
        logging.info("migrate: rows=%d", n)
    elif args.cmd == "validate":
        _validate(ROOT)


if __name__ == "__main__":
    main()
