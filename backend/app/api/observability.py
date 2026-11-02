"""Observability, traces, and metrics query endpoints."""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.db.session import get_db
from app.db.models import User
from app.api.deps import get_current_user
from app.observability.service import ObservabilityService

router = APIRouter()


class TraceResponse(BaseModel):
    id: str
    conversation_id: str | None
    query: str
    stages: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    total_latency_ms: float
    created_at: str


@router.get("/traces", response_model=List[TraceResponse])
async def get_traces(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    obs_svc = ObservabilityService(db)
    traces = await obs_svc.get_traces(user.id, limit=limit)
    return [
        TraceResponse(
            id=t.id,
            conversation_id=t.conversation_id,
            query=t.query,
            stages=t.stages or [],
            tool_calls=t.tool_calls or [],
            total_latency_ms=t.total_latency_ms,
            created_at=t.created_at.isoformat() if t.created_at else ""
        ) for t in traces
    ]


@router.get("/metrics")
async def get_metrics(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    obs_svc = ObservabilityService(db)
    return await obs_svc.get_system_metrics(user.id)
