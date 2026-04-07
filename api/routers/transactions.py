import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_fraud_detector, get_n8n_client
from models.transaction import Transaction, FraudAlert
from schemas import TransactionIn, TransactionOut, FraudScoreOut
from services.fraud_detector import FraudDetector
from services.n8n_client import N8nClient
from config import settings

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post(
    "/",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a transaction for fraud analysis",
)
async def create_transaction(
    tx_in: TransactionIn,
    db: AsyncSession = Depends(get_db),
    detector: FraudDetector = Depends(get_fraud_detector),
    n8n: N8nClient = Depends(get_n8n_client),
):
    # Fetch user profile for contextual scoring
    profile = await detector.get_user_profile(tx_in.user_id)
    history_country = profile["known_countries"][0] if profile["known_countries"] else None

    # Score the transaction
    result = await detector.score(
        tx_in,
        user_history_country=history_country,
        user_known_devices=profile["known_devices"],
    )

    is_fraud = result["decision"] in ("block", "review")
    db_tx = Transaction(
        external_id=tx_in.external_id,
        user_id=tx_in.user_id,
        merchant_id=tx_in.merchant_id,
        merchant_category=tx_in.merchant_category,
        amount=tx_in.amount,
        currency=tx_in.currency,
        country=tx_in.country,
        city=tx_in.city,
        ip_address=tx_in.ip_address,
        channel=tx_in.channel,
        device_fingerprint=tx_in.device_fingerprint,
        fraud_score=result["fraud_score"],
        is_fraud=is_fraud,
        fraud_reasons=json.dumps(result["reasons"]),
        status="blocked" if result["decision"] == "block" else (
            "review" if result["decision"] == "review" else "approved"
        ),
    )
    db.add(db_tx)
    await db.flush()  # get db_tx.id

    # Create alert + notify n8n for suspicious transactions
    if result["decision"] in ("block", "review"):
        alert = FraudAlert(
            transaction_id=db_tx.id,
            user_id=tx_in.user_id,
            alert_type="high_score" if result["fraud_score"] >= settings.FRAUD_SCORE_HIGH else "review_required",
            severity=result["severity"],
            fraud_score=result["fraud_score"],
            details=json.dumps(result["reasons"]),
        )
        db.add(alert)
        await db.flush()

        payload = n8n.build_alert_payload(
            transaction_id=db_tx.id,
            user_id=tx_in.user_id,
            amount=tx_in.amount,
            currency=tx_in.currency,
            fraud_score=result["fraud_score"],
            severity=result["severity"],
            decision=result["decision"],
            reasons=result["reasons"],
            merchant_id=tx_in.merchant_id,
            country=tx_in.country,
        )
        notified = await n8n.send_fraud_alert(payload)
        if notified:
            alert.notified = True
            alert.notified_at = datetime.utcnow()

    # Update user profile (async, best-effort)
    await detector.update_user_profile(tx_in.user_id, tx_in)

    return db_tx


@router.get(
    "/{transaction_id}",
    response_model=TransactionOut,
    summary="Get transaction details and fraud score",
)
async def get_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    tx = await db.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@router.get(
    "/",
    response_model=list[TransactionOut],
    summary="List transactions (optionally filtered by user)",
)
async def list_transactions(
    user_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
):
    q = select(Transaction).order_by(desc(Transaction.created_at)).limit(limit).offset(offset)
    if user_id:
        q = q.where(Transaction.user_id == user_id)
    if status:
        q = q.where(Transaction.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/score",
    response_model=FraudScoreOut,
    summary="Dry-run fraud scoring without persisting a transaction",
)
async def score_only(
    tx_in: TransactionIn,
    detector: FraudDetector = Depends(get_fraud_detector),
):
    profile = await detector.get_user_profile(tx_in.user_id)
    history_country = profile["known_countries"][0] if profile["known_countries"] else None
    result = await detector.score(
        tx_in,
        user_history_country=history_country,
        user_known_devices=profile["known_devices"],
    )
    return result
