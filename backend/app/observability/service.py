"""Observability tracing service and metrics logger."""
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.models import ExecutionTrace


class ObservabilityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_trace(
        self,
        user_id: str,
        conversation_id: Optional[str],
        query: str,
        stages: List[Dict[str, Any]],
        tool_calls: List[Dict[str, Any]],
        total_latency_ms: float,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        token_usage: Optional[Dict[str, Any]] = None
    ) -> ExecutionTrace:
        trace = ExecutionTrace(
            user_id=user_id,
            conversation_id=conversation_id,
            query=query,
            stages=stages,
            tool_calls=tool_calls,
            total_latency_ms=round(total_latency_ms, 2),
            model_provider=model_provider,
            model_name=model_name,
            token_usage=token_usage or {"total_tokens": 0}
        )
        self.db.add(trace)
        await self.db.commit()
        await self.db.refresh(trace)
        return trace

    async def get_traces(self, user_id: str, limit: int = 20) -> List[ExecutionTrace]:
        stmt = (
            select(ExecutionTrace)
            .where(ExecutionTrace.user_id == user_id)
            .order_by(ExecutionTrace.created_at.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_system_metrics(self, user_id: str) -> Dict[str, Any]:
        stmt = select(
            func.count(ExecutionTrace.id),
            func.avg(ExecutionTrace.total_latency_ms)
        ).where(ExecutionTrace.user_id == user_id)
        res = await self.db.execute(stmt)
        count, avg_latency = res.first() or (0, 0.0)

        return {
            "total_queries_executed": count or 0,
            "average_latency_ms": round(avg_latency or 0.0, 2),
            "status": "healthy"
        }
