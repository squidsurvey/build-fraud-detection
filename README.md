# Fraud Detection MVP

Rule-based fraud detection service with FastAPI, n8n workflow automation, PostgreSQL, and Redis — fully containerised with Docker Compose.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Docker Compose                      │
│                                                         │
│  ┌──────────────┐     ┌──────────────┐                 │
│  │  FastAPI     │────▶│   n8n        │                 │
│  │  :8000       │     │   :5678      │                 │
│  └──────┬───────┘     └──────────────┘                 │
│         │                                               │
│  ┌──────▼───────┐     ┌──────────────┐                 │
│  │  PostgreSQL  │     │    Redis     │                 │
│  │  :5432       │     │   :6379      │                 │
│  └──────────────┘     └──────────────┘                 │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your secrets

# 2. Start all services
docker compose up -d --build

# 3. API docs
open http://localhost:8000/docs

# 4. n8n UI (admin / n8n_secret by default)
open http://localhost:5678
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/transactions/` | Submit transaction for fraud analysis |
| POST | `/api/v1/transactions/score` | Dry-run score (no persistence) |
| GET | `/api/v1/transactions/{id}` | Get transaction details |
| GET | `/api/v1/transactions/` | List transactions |
| GET | `/api/v1/alerts/` | List fraud alerts |
| PATCH | `/api/v1/alerts/{id}/resolve` | Resolve an alert |
| GET | `/health` | Service health check |

## Example: Submit a Transaction

```bash
curl -X POST http://localhost:8000/api/v1/transactions/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "amount": 9500.00,
    "currency": "USD",
    "merchant_id": "merchant_456",
    "merchant_category": "cryptocurrency",
    "country": "RU",
    "channel": "web",
    "device_fingerprint": "fp_abc123"
  }'
```

## Fraud Scoring

Transactions receive a score from 0 to 1 based on:

| Signal | Weight |
|--------|--------|
| High amount (>$5,000) | 30% |
| Velocity breach (>10 tx/hour) | 25% |
| Cross-border transaction | 15% |
| High-risk merchant category | 15% |
| Country mismatch vs. history | 20% |
| New/unknown device | 10% |
| Unusual hour (00-05 UTC) | 10% |
| Round amount | 5% |

**Decisions:**
- `approve` — score < 0.50
- `review` — score 0.50–0.74
- `block` — score ≥ 0.75

## n8n Integration

When a transaction scores ≥ 0.50, the API sends a webhook to n8n at `/webhook/fraud-alert`.

Import `n8n/workflows/fraud_alert_workflow.json` into n8n to activate the pipeline. The workflow:
1. Receives the fraud alert
2. Routes by severity
3. Formats notification message
4. Can be extended with email/Slack/PagerDuty nodes

## n8n Workflow Import

1. Open n8n at `http://localhost:5678`
2. Settings → Workflows → Import from file
3. Select `n8n/workflows/fraud_alert_workflow.json`
4. Activate the workflow
