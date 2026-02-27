# MCP Trade Plan Service

Minimal REST service for managing trade plans.

## Endpoints

- `POST /trade-plans`
- `GET /trade-plans?account_id=&strategy_id=&status=`
- `GET /trade-plans/{id}`
- `POST /trade-plans/{id}/close`
- `POST /trade-plans/{id}/cancel`

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Example create payload

```json
{
  "account_id": "paper-1",
  "strategy_id": "signal_calls_v1",
  "signal": {
    "signal_id": "sig-2026-02-26-145500",
    "source": "model_x",
    "ts": "2026-02-26T21:55:00Z"
  },
  "instrument": {
    "underlying": "TSLA",
    "type": "option",
    "selector": {
      "ticker": "TSLA240503P00115000"
    }
  },
  "entry": {
    "qty": 2,
    "order": {
      "type": "limit",
      "cancel_if_not_filled_sec": 45
    },
    "max_debit_usd": 400
  },
  "take_profit": {
    "mode": "percent",
    "pct": 0.3,
    "order": {
      "type": "limit",
      "limit_price_method": "mid",
      "time_in_force": "gtc"
    }
  },
  "position_rules": {
    "max_open_plans_per_underlying": 1,
    "close_on_expiry_days_lte": 1
  },
  "idempotency_key": "signal_calls_v1:paper-1:sig-2026-02-26-145500"
}
```
