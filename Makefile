.PHONY: install seed run migrate query test lint line-count report dashboard all clean

install:
	uv venv --python 3.11
	uv pip install -r requirements.txt
	uv pip install -e .

seed:
	uv run python -m mal_payments.run seed

run:
	uv run python -m mal_payments.run ingest

migrate:
	uv run python -m mal_payments.run migrate

query:
	@echo "=== 01: Daily volume by payment type ==="
	@uv run python -c "import duckdb; print(duckdb.sql(open('sql/01_daily_volume_by_payment_type.sql').read()).df())"
	@echo "\n=== 02: Failure breakdown by squad ==="
	@uv run python -c "import duckdb; print(duckdb.sql(open('sql/02_failure_breakdown_by_squad.sql').read()).df())"
	@echo "\n=== 03: Auth-to-settlement latency ==="
	@uv run python -c "import duckdb; print(duckdb.sql(open('sql/03_authorization_to_settlement_latency.sql').read()).df())"
	@echo "\n=== 04: Cross-product customer 360 ==="
	@uv run python -c "import duckdb; print(duckdb.sql(open('sql/04_cross_product_customer_360.sql').read()).df())"
	@echo "\n=== 05: Currency exposure / remittance corridors ==="
	@uv run python -c "import duckdb; print(duckdb.sql(open('sql/05_currency_exposure_remittance_corridors.sql').read()).df())"

test:
	uv run pytest

lint:
	uv run ruff check src/ tests/

line-count:
	@./scripts/line_count_check.sh

report:
	uv run quarto render docs/report.qmd

dashboard:
	uv run streamlit run dashboard/app.py

all: install seed run migrate test line-count

clean:
	rm -rf data/output/canonical/* data/output/quarantine/*
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
