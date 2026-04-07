"""
n8n webhook client — fires fraud alert events to n8n workflows.
"""
import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)


class N8nClient:
    def __init__(self):
        self._webhook_url = settings.N8N_WEBHOOK_URL
        self._timeout = httpx.Timeout(10.0, connect=5.0)

    async def send_fraud_alert(self, payload: dict) -> bool:
        """
        POST a fraud alert to the n8n webhook.
        Returns True on success, False on failure (non-blocking).
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(self._webhook_url, json=payload)
                resp.raise_for_status()
                logger.info("n8n alert sent | transaction=%s score=%.3f",
                            payload.get("transaction_id"), payload.get("fraud_score"))
                return True
        except httpx.HTTPStatusError as exc:
            logger.error("n8n webhook HTTP error: %s", exc)
        except httpx.RequestError as exc:
            logger.error("n8n webhook connection error: %s", exc)
        return False

    def build_alert_payload(
        self,
        transaction_id: str,
        user_id: str,
        amount: float,
        currency: str,
        fraud_score: float,
        severity: str,
        decision: str,
        reasons: list[str],
        merchant_id: str | None = None,
        country: str | None = None,
    ) -> dict:
        return {
            "event": "fraud_alert",
            "transaction_id": str(transaction_id),
            "user_id": user_id,
            "merchant_id": merchant_id,
            "amount": amount,
            "currency": currency,
            "fraud_score": fraud_score,
            "severity": severity,
            "decision": decision,
            "reasons": reasons,
            "country": country,
            "dashboard_url": f"http://localhost:8000/api/v1/transactions/{transaction_id}",
        }
