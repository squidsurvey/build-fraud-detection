import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.transaction import FraudAlert
from schemas import AlertOut, AlertResolveIn

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get(
    "/",
    response_model=list[AlertOut],
    summary="List fraud alerts",
)
async def list_alerts(
    user_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    resolved: Optional[bool] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
):
    q = select(FraudAlert).order_by(desc(FraudAlert.created_at)).limit(limit).offset(offset)
    if user_id:
        q = q.where(FraudAlert.user_id == user_id)
    if severity:
        q = q.where(FraudAlert.severity == severity)
    if resolved is not None:
        q = q.where(FraudAlert.resolved == resolved)
    result = await db.execute(q)
    return result.scalars().all()


@router.get(
    "/{alert_id}",
    response_model=AlertOut,
    summary="Get a specific fraud alert",
)
async def get_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    alert = await db.get(FraudAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.patch(
    "/{alert_id}/resolve",
    response_model=AlertOut,
    summary="Resolve / dismiss a fraud alert",
)
async def resolve_alert(
    alert_id: uuid.UUID,
    body: AlertResolveIn,
    db: AsyncSession = Depends(get_db),
):
    alert = await db.get(FraudAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.resolved:
        raise HTTPException(status_code=409, detail="Alert already resolved")
    alert.resolved = True
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = body.resolved_by
    alert.resolution_note = body.resolution_note
    return alert
