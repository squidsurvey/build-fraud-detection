from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ── Inbound ───────────────────────────────────────────────────────────────────

class TransactionIn(BaseModel):
    external_id: Optional[str] = None
    user_id: str = Field(..., min_length=1, max_length=128)
    merchant_id: Optional[str] = None
    merchant_category: Optional[str] = None
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=8)
    country: Optional[str] = Field(default=None, max_length=4)
    city: Optional[str] = None
    ip_address: Optional[str] = None
    channel: Optional[str] = None
    device_fingerprint: Optional[str] = None


class AlertResolveIn(BaseModel):
    resolved_by: str
    resolution_note: Optional[str] = None


# ── Outbound ──────────────────────────────────────────────────────────────────

class FraudScoreOut(BaseModel):
    fraud_score: float
    decision: str
    severity: str
    reasons: list[str]


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: Optional[str]
    user_id: str
    merchant_id: Optional[str]
    amount: float
    currency: str
    country: Optional[str]
    channel: Optional[str]
    fraud_score: Optional[float]
    is_fraud: Optional[bool]
    fraud_reasons: Optional[str]
    status: str
    created_at: datetime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    user_id: str
    alert_type: str
    severity: str
    fraud_score: float
    details: Optional[str]
    notified: bool
    resolved: bool
    created_at: datetime


class HealthOut(BaseModel):
    status: str
    db: str
    redis: str
    version: str = "1.0.0"
