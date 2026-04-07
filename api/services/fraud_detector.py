"""
Fraud Detection Engine — MVP implementation.

Scoring pipeline:
  1. Rule-based checks (fast, deterministic)
  2. Velocity / frequency analysis (Redis-backed)
  3. Composite weighted score → decision
"""
import json
import math
from datetime import datetime, timedelta
from typing import Optional
import redis.asyncio as aioredis

from config import settings
from schemas import TransactionIn


# ── Risk weights ─────────────────────────────────────────────────────────────
WEIGHTS = {
    "high_amount": 0.30,
    "velocity_breach": 0.25,
    "unusual_hour": 0.10,
    "country_mismatch": 0.20,
    "new_device": 0.10,
    "high_risk_category": 0.15,
    "round_amount": 0.05,
    "cross_border": 0.15,
}

HIGH_RISK_CATEGORIES = {
    "gambling", "cryptocurrency", "money_transfer",
    "wire_transfer", "prepaid_card", "adult_content",
}

# Typical per-transaction amount threshold (USD-equivalent)
HIGH_AMOUNT_THRESHOLD = 5_000.0


class FraudDetector:
    def __init__(self, redis_client: aioredis.Redis):
        self._redis = redis_client

    # ── Public API ────────────────────────────────────────────────────────────

    async def score(
        self,
        tx: TransactionIn,
        user_history_country: Optional[str] = None,
        user_known_devices: Optional[list[str]] = None,
    ) -> dict:
        """Return fraud_score (0-1), decision, and reasons list."""
        reasons: list[str] = []
        raw_score = 0.0

        # 1 – Amount check
        if tx.amount >= HIGH_AMOUNT_THRESHOLD:
            factor = min(tx.amount / HIGH_AMOUNT_THRESHOLD, 3.0) / 3.0
            raw_score += WEIGHTS["high_amount"] * factor
            reasons.append(f"high_amount:{tx.amount:.2f}")

        # 2 – Velocity (transactions per window for this user)
        velocity_score = await self._velocity_score(tx.user_id)
        if velocity_score > 0:
            raw_score += WEIGHTS["velocity_breach"] * velocity_score
            reasons.append("velocity_breach")

        # 3 – Unusual hour (00:00 – 05:00 UTC)
        hour = datetime.utcnow().hour
        if hour < 5:
            raw_score += WEIGHTS["unusual_hour"]
            reasons.append(f"unusual_hour:{hour}h_utc")

        # 4 – Country mismatch vs. known history
        if user_history_country and tx.country and tx.country != user_history_country:
            raw_score += WEIGHTS["country_mismatch"]
            reasons.append(f"country_mismatch:{user_history_country}->{tx.country}")

        # 5 – New / unknown device
        if tx.device_fingerprint and user_known_devices is not None:
            if tx.device_fingerprint not in user_known_devices:
                raw_score += WEIGHTS["new_device"]
                reasons.append("new_device")

        # 6 – High-risk merchant category
        if tx.merchant_category and tx.merchant_category.lower() in HIGH_RISK_CATEGORIES:
            raw_score += WEIGHTS["high_risk_category"]
            reasons.append(f"high_risk_category:{tx.merchant_category}")

        # 7 – Suspiciously round amount (e.g. 1000.00, 5000.00)
        if tx.amount > 100 and tx.amount % 500 == 0:
            raw_score += WEIGHTS["round_amount"]
            reasons.append("round_amount")

        # 8 – Cross-border transaction
        if tx.country and tx.country not in ("US", "CA"):
            raw_score += WEIGHTS["cross_border"]
            reasons.append(f"cross_border:{tx.country}")

        # Clamp to [0, 1]
        fraud_score = min(raw_score, 1.0)

        # Register transaction in velocity window
        await self._register_transaction(tx.user_id)

        # Decision
        if fraud_score >= settings.FRAUD_SCORE_HIGH:
            decision = "block"
            severity = "high" if fraud_score >= 0.9 else "medium"
        elif fraud_score >= settings.FRAUD_SCORE_MEDIUM:
            decision = "review"
            severity = "medium"
        else:
            decision = "approve"
            severity = "low"

        return {
            "fraud_score": round(fraud_score, 4),
            "decision": decision,
            "severity": severity,
            "reasons": reasons,
        }

    # ── Velocity helpers ──────────────────────────────────────────────────────

    async def _velocity_score(self, user_id: str) -> float:
        key = f"velocity:{user_id}"
        count = await self._redis.get(key)
        count = int(count) if count else 0
        if count >= settings.VELOCITY_MAX_TRANSACTIONS:
            excess = count - settings.VELOCITY_MAX_TRANSACTIONS
            return min(1.0, 0.5 + excess * 0.1)
        return 0.0

    async def _register_transaction(self, user_id: str):
        key = f"velocity:{user_id}"
        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, settings.VELOCITY_WINDOW_SECONDS)
        await pipe.execute()

    # ── User profile helpers ──────────────────────────────────────────────────

    async def get_user_profile(self, user_id: str) -> dict:
        key = f"profile:{user_id}"
        data = await self._redis.get(key)
        if data:
            return json.loads(data)
        return {"known_countries": [], "known_devices": [], "transaction_count": 0}

    async def update_user_profile(self, user_id: str, tx: TransactionIn):
        profile = await self.get_user_profile(user_id)
        if tx.country and tx.country not in profile["known_countries"]:
            profile["known_countries"].append(tx.country)
        if tx.device_fingerprint and tx.device_fingerprint not in profile["known_devices"]:
            profile["known_devices"].append(tx.device_fingerprint)
        profile["transaction_count"] += 1
        key = f"profile:{user_id}"
        await self._redis.setex(key, 86400 * 90, json.dumps(profile))  # 90-day TTL
