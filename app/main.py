from datetime import datetime, timezone
from threading import Lock
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict


app = FastAPI(title="MCP Trade Plan Service", version="1.0.0")


class Signal(BaseModel):
    signal_id: str
    source: str
    ts: datetime

    model_config = ConfigDict(extra="forbid")


class Selector(BaseModel):
    ticker: str

    model_config = ConfigDict(extra="forbid")


class Instrument(BaseModel):
    underlying: str
    type: Literal["option"]
    selector: Selector

    model_config = ConfigDict(extra="forbid")


class EntryOrder(BaseModel):
    type: Literal["limit"]
    cancel_if_not_filled_sec: int

    model_config = ConfigDict(extra="forbid")


class Entry(BaseModel):
    qty: int
    order: EntryOrder
    max_debit_usd: float

    model_config = ConfigDict(extra="forbid")


class TakeProfitOrder(BaseModel):
    type: Literal["limit"]
    limit_price_method: Literal["mid"]
    time_in_force: Literal["gtc"]

    model_config = ConfigDict(extra="forbid")


class TakeProfit(BaseModel):
    mode: Literal["percent"]
    pct: float
    order: TakeProfitOrder

    model_config = ConfigDict(extra="forbid")


class PositionRules(BaseModel):
    max_open_plans_per_underlying: int
    close_on_expiry_days_lte: int

    model_config = ConfigDict(extra="forbid")


class TradePlanCreate(BaseModel):
    account_id: str
    strategy_id: str
    signal: Signal
    instrument: Instrument
    entry: Entry
    take_profit: TakeProfit
    position_rules: PositionRules
    idempotency_key: str

    model_config = ConfigDict(extra="forbid")


class TradePlan(TradePlanCreate):
    id: str
    status: Literal["open", "closed", "cancelled"]
    created_at: datetime
    updated_at: datetime


class StatusResponse(BaseModel):
    id: str
    status: Literal["open", "closed", "cancelled"]
    updated_at: datetime


_store_lock = Lock()
_plans: dict[str, TradePlan] = {}
_idempotency_index: dict[str, str] = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/trade-plans", response_model=TradePlan, status_code=status.HTTP_201_CREATED)
def create_trade_plan(payload: TradePlanCreate, response: Response) -> TradePlan:
    with _store_lock:
        existing_id = _idempotency_index.get(payload.idempotency_key)
        if existing_id is not None:
            response.status_code = status.HTTP_200_OK
            return _plans[existing_id]

        now = _utc_now()
        plan = TradePlan(
            **payload.model_dump(),
            id=f"tp-{uuid4().hex}",
            status="open",
            created_at=now,
            updated_at=now,
        )
        _plans[plan.id] = plan
        _idempotency_index[payload.idempotency_key] = plan.id
        return plan


@app.get("/trade-plans", response_model=list[TradePlan])
def list_trade_plans(
    account_id: str | None = Query(default=None),
    strategy_id: str | None = Query(default=None),
    status: Literal["open", "closed", "cancelled"] | None = Query(default=None),
) -> list[TradePlan]:
    with _store_lock:
        plans = list(_plans.values())

    if account_id is not None:
        plans = [p for p in plans if p.account_id == account_id]
    if strategy_id is not None:
        plans = [p for p in plans if p.strategy_id == strategy_id]
    if status is not None:
        plans = [p for p in plans if p.status == status]

    return plans


@app.get("/trade-plans/{id}", response_model=TradePlan)
def get_trade_plan(id: str) -> TradePlan:
    with _store_lock:
        plan = _plans.get(id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Trade plan not found")
        return plan


@app.post("/trade-plans/{id}/close", response_model=StatusResponse)
def close_trade_plan(id: str) -> StatusResponse:
    with _store_lock:
        plan = _plans.get(id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Trade plan not found")
        if plan.status != "open":
            raise HTTPException(status_code=409, detail="Only open plans can be closed")
        plan.status = "closed"
        plan.updated_at = _utc_now()
        _plans[id] = plan
        return StatusResponse(id=plan.id, status=plan.status, updated_at=plan.updated_at)


@app.post("/trade-plans/{id}/cancel", response_model=StatusResponse)
def cancel_trade_plan(id: str) -> StatusResponse:
    with _store_lock:
        plan = _plans.get(id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Trade plan not found")
        if plan.status != "open":
            raise HTTPException(status_code=409, detail="Only open plans can be cancelled")
        plan.status = "cancelled"
        plan.updated_at = _utc_now()
        _plans[id] = plan
        return StatusResponse(id=plan.id, status=plan.status, updated_at=plan.updated_at)
