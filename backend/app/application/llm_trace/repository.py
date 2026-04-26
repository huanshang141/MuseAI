from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.postgres.models.llm_trace import LLMTraceEvent


class LLMTraceEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_event(self, event_data: dict[str, Any]) -> LLMTraceEvent:
        event = LLMTraceEvent(**event_data)
        self._session.add(event)
        await self._session.commit()
        return event

    async def list_events(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[LLMTraceEvent]:
        stmt = select(LLMTraceEvent).order_by(LLMTraceEvent.created_at.desc())
        if filters:
            if filters.get("source"):
                stmt = stmt.where(LLMTraceEvent.source == filters["source"])
            if filters.get("model"):
                stmt = stmt.where(LLMTraceEvent.model == filters["model"])
            if filters.get("status"):
                stmt = stmt.where(LLMTraceEvent.status == filters["status"])
            if filters.get("trace_id"):
                stmt = stmt.where(LLMTraceEvent.trace_id == filters["trace_id"])
            if filters.get("start_at"):
                stmt = stmt.where(LLMTraceEvent.created_at >= filters["start_at"])
            if filters.get("end_at"):
                stmt = stmt.where(LLMTraceEvent.created_at <= filters["end_at"])
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_events(self, filters: dict[str, Any] | None = None) -> int:
        stmt = select(LLMTraceEvent)
        if filters:
            if filters.get("source"):
                stmt = stmt.where(LLMTraceEvent.source == filters["source"])
            if filters.get("model"):
                stmt = stmt.where(LLMTraceEvent.model == filters["model"])
            if filters.get("status"):
                stmt = stmt.where(LLMTraceEvent.status == filters["status"])
            if filters.get("trace_id"):
                stmt = stmt.where(LLMTraceEvent.trace_id == filters["trace_id"])
            if filters.get("start_at"):
                stmt = stmt.where(LLMTraceEvent.created_at >= filters["start_at"])
            if filters.get("end_at"):
                stmt = stmt.where(LLMTraceEvent.created_at <= filters["end_at"])
        result = await self._session.execute(stmt)
        return len(result.scalars().all())

    async def get_by_call_id(self, call_id: str) -> LLMTraceEvent | None:
        stmt = select(LLMTraceEvent).where(LLMTraceEvent.call_id == call_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
