"""
Fraud Detection API — FastAPI entry point.
"""
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import settings
from database import create_tables, AsyncSessionLocal
from routers import transactions_router, alerts_router
from schemas import HealthOut

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────
    logger.info("Starting Fraud Detection API...")

    # Redis connection pool
    app.state.redis = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )

    # DB tables (idempotent)
    await create_tables()
    logger.info("Database tables ready.")

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────
    await app.state.redis.aclose()
    logger.info("Fraud Detection API stopped.")


app = FastAPI(
    title="Fraud Detection API",
    description=(
        "MVP fraud detection service with rule-based scoring, "
        "velocity checks, and n8n workflow integration."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")


# ── Health check ───────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthOut, tags=["system"])
async def health():
    db_status = "ok"
    redis_status = "ok"

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"

    try:
        from fastapi import Request  # noqa
        # Direct ping using settings
        r = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        await r.ping()
        await r.aclose()
    except Exception as exc:
        redis_status = f"error: {exc}"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return HealthOut(status=overall, db=db_status, redis=redis_status)


@app.get("/", tags=["system"])
async def root():
    return {
        "service": "Fraud Detection API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
