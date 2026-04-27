"""Canonical Payment Event v1. Legacy schema, kept ONLY for the migration demo.

v1 stored amount as float USD. Float rounding errors in reconciliation
forced the move to integer minor units in v2. New code uses v2.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .canonical_v2 import CounterpartyType, PaymentType, SourceSquad, Status


class CanonicalPaymentEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    schema_version: Literal["v1"] = "v1"
    source_squad: SourceSquad
    source_event_id: str
    correlation_id: str
    idempotency_key: str

    payment_type: PaymentType
    event_type: str

    amount: float = Field(..., ge=0.0, description="USD amount (float, the v1 problem)")

    customer_id: str
    counterparty_type: CounterpartyType
    counterparty_id: str
    counterparty_name: Optional[str] = None
    counterparty_metadata: dict[str, Any] = Field(default_factory=dict)

    status: Status
    status_reason: Optional[str] = None
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    event_timestamp: datetime

    payment_method_details: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any]
    ingested_at: datetime
    pipeline_version: str
