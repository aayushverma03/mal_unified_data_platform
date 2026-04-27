"""Canonical Payment Event v2. Single source of truth.

Event-grain (auth and capture linked by ``correlation_id``), integer
minor units (``amount_minor``), ``raw_payload`` preserved, and
``payment_method_details`` as a JSON bag. Defended in
docs/architecture.pdf.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PaymentType = Literal["card", "transfer", "bill_payment"]
SourceSquad = Literal["cards", "transfers", "bill_payments"]
Status = Literal[
    "initiated", "pending", "authorized", "settled",
    "failed", "reversed", "refunded",
]
CounterpartyType = Literal["merchant", "account", "biller"]


class CanonicalPaymentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # --- Identity & lineage ---
    event_id: str = Field(..., description="ULID for this event row")
    schema_version: Literal["v2"] = "v2"
    source_squad: SourceSquad
    source_event_id: str
    correlation_id: str = Field(..., description="Links auth->capture->refund")
    idempotency_key: str = Field(..., description="Deterministic dedup hash")

    # --- Classification ---
    payment_type: PaymentType
    event_type: str

    # --- Money (integer minor units only) ---
    amount_minor: int = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3)
    amount_usd_minor: Optional[int] = None
    fx_rate: Optional[Decimal] = None
    fx_timestamp: Optional[datetime] = None

    # --- Parties ---
    customer_id: str
    counterparty_type: CounterpartyType
    counterparty_id: str
    counterparty_name: Optional[str] = None
    counterparty_metadata: dict[str, Any] = Field(default_factory=dict)

    # --- Lifecycle ---
    status: Status
    status_reason: Optional[str] = None
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    event_timestamp: datetime

    # --- Extensibility & debug ---
    payment_method_details: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any]
    ingested_at: datetime
    pipeline_version: str
