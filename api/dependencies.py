from functools import lru_cache
import redis.asyncio as aioredis
from fastapi import Request
from services.fraud_detector import FraudDetector
from services.n8n_client import N8nClient


def get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis


def get_fraud_detector(request: Request) -> FraudDetector:
    return FraudDetector(redis_client=request.app.state.redis)


def get_n8n_client() -> N8nClient:
    return N8nClient()
