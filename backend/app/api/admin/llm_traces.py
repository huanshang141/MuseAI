from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentAdminUser, SessionDep
from app.application.llm_trace.repository import LLMTraceEventRepository

router = APIRouter(prefix="/admin/llm-traces", tags=["admin-llm-traces"])


class LLMTraceSummary(BaseModel):
    call_id: str
    created_at: datetime
    source: str
    model: str
    duration_ms: int | None
    total_tokens: int | None
    status: str
    trace_id: str | None
    request_id: str | None

    model_config = {"from_attributes": True}


class LLMTraceListResponse(BaseModel):
    items: list[LLMTraceSummary]
    total: int
    limit: int
    offset: int


class LLMTraceDetailResponse(BaseModel):
    call_id: str
    request_id: str | None
    trace_id: str | None
    source: str
    endpoint_method: str | None
    endpoint_path: str | None
    actor_type: str | None
    actor_id: str | None
    session_type: str | None
    session_id: str | None
    provider: str
    base_url: str | None
    model: str
    request_payload_masked: dict[str, Any] | None
    response_payload_masked: dict[str, Any] | None
    request_readable: str | None
    response_readable: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    status: str
    error_type: str | None
    error_message_masked: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=LLMTraceListResponse)
async def list_llm_traces(
    admin: CurrentAdminUser,
    session: SessionDep,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: str | None = Query(None),
    model: str | None = Query(None),
    status: str | None = Query(None),
    trace_id: str | None = Query(None),
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> LLMTraceListResponse:
    repo = LLMTraceEventRepository(session)
    filters = {
        k: v
        for k, v in {
            "source": source,
            "model": model,
            "status": status,
            "trace_id": trace_id,
            "start_at": start_at,
            "end_at": end_at,
        }.items()
        if v is not None
    }
    items = await repo.list_events(filters=filters, limit=limit, offset=offset)
    total = await repo.count_events(filters=filters)
    return LLMTraceListResponse(
        items=[
            LLMTraceSummary(
                call_id=i.call_id,
                created_at=i.created_at,
                source=i.source,
                model=i.model,
                duration_ms=i.duration_ms,
                total_tokens=i.total_tokens,
                status=i.status,
                trace_id=i.trace_id,
                request_id=i.request_id,
            )
            for i in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{call_id}", response_model=LLMTraceDetailResponse)
async def get_llm_trace_detail(
    admin: CurrentAdminUser,
    session: SessionDep,
    call_id: str,
) -> LLMTraceDetailResponse:
    repo = LLMTraceEventRepository(session)
    event = await repo.get_by_call_id(call_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    return LLMTraceDetailResponse(
        call_id=event.call_id,
        request_id=event.request_id,
        trace_id=event.trace_id,
        source=event.source,
        endpoint_method=event.endpoint_method,
        endpoint_path=event.endpoint_path,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        session_type=event.session_type,
        session_id=event.session_id,
        provider=event.provider,
        base_url=event.base_url,
        model=event.model,
        request_payload_masked=event.request_payload_masked,
        response_payload_masked=event.response_payload_masked,
        request_readable=event.request_readable,
        response_readable=event.response_readable,
        prompt_tokens=event.prompt_tokens,
        completion_tokens=event.completion_tokens,
        total_tokens=event.total_tokens,
        started_at=event.started_at,
        ended_at=event.ended_at,
        duration_ms=event.duration_ms,
        status=event.status,
        error_type=event.error_type,
        error_message_masked=event.error_message_masked,
        created_at=event.created_at,
    )
