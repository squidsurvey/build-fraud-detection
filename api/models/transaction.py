import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(128), unique=True, nullable=True, index=True)

    # Parties
    user_id = Column(String(128), nullable=False, index=True)
    merchant_id = Column(String(128), nullable=True, index=True)
    merchant_category = Column(String(64), nullable=True)

    # Amount & currency
    amount = Column(Float, nullable=False)
    currency = Column(String(8), nullable=False, default="USD")

    # Location
    country = Column(String(4), nullable=True)
    city = Column(String(128), nullable=True)
    ip_address = Column(String(64), nullable=True)

    # Device / channel
    channel = Column(String(32), nullable=True)  # web, mobile, atm, pos
    device_fingerprint = Column(String(256), nullable=True)

    # Fraud scores & decision
    fraud_score = Column(Float, nullable=True)
    is_fraud = Column(Boolean, nullable=True)
    fraud_reasons = Column(Text, nullable=True)  # JSON array as text

    # Status
    status = Column(String(32), nullable=False, default="pending")  # pending, approved, blocked, review

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_transactions_user_created", "user_id", "created_at"),
    )


class FraudAlert(Base):
    __tablename__ = "fraud_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(String(128), nullable=False, index=True)

    alert_type = Column(String(64), nullable=False)  # high_score, velocity, pattern
    severity = Column(String(16), nullable=False)     # low, medium, high, critical
    fraud_score = Column(Float, nullable=False)
    details = Column(Text, nullable=True)             # JSON payload

    # n8n notification status
    notified = Column(Boolean, default=False)
    notified_at = Column(DateTime, nullable=True)

    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(128), nullable=True)
    resolution_note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
