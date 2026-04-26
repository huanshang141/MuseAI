from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.application.llm_trace.context import get_trace_context
from app.application.llm_trace.formatter import to_readable_request, to_readable_response
from app.application.llm_trace.masking import mask_json, mask_text, mask_url

logger = logging.getLogger(__name__)


class LLMTraceRecorder:
    def __init__(self, session_maker: Any | None = None) -> None:
        self._session_maker = session_maker

    async def record_call_start(
        self,
        call_id: str,
        provider: str,
        model: str,
        base_url: str | None = None,
        request_payload: dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        pass

    async def record_call_success(
        self,
        call_id: str,
        response_payload: dict[str, Any] | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        **extra: Any,
    ) -> None:
        await self._persist(
            call_id=call_id,
            status="success",
            response_payload=response_payload,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            started_at=started_at,
            ended_at=ended_at,
            **extra,
        )

    async def record_call_error(
        self,
        call_id: str,
        error_type: str,
        error_message: str,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        **extra: Any,
    ) -> None:
        await self._persist(
            call_id=call_id,
            status="error",
            error_type=error_type,
            error_message=error_message,
            started_at=started_at,
            ended_at=ended_at,
            **extra,
        )

    async def record_call_once(
        self,
        call_id: str,
        provider: str,
        model: str,
        status: str,
        base_url: str | None = None,
        request_payload: dict[str, Any] | None = None,
        response_payload: dict[str, Any] | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        **extra: Any,
    ) -> None:
        await self._persist(
            call_id=call_id,
            provider=provider,
            model=model,
            status=status,
            base_url=base_url,
            request_payload=request_payload,
            response_payload=response_payload,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            error_type=error_type,
            error_message=error_message,
            started_at=started_at,
            ended_at=ended_at,
            **extra,
        )

    async def _persist(self, **kwargs: Any) -> None:
        try:
            ctx = get_trace_context()
            payload: dict[str, Any] = {}
            for key in (
                "request_id",
                "trace_id",
                "source",
                "endpoint_method",
                "endpoint_path",
                "actor_type",
                "actor_id",
                "session_type",
                "session_id",
            ):
                payload[key] = kwargs.pop(key, None) or ctx.get(key)

            provider = kwargs.get("provider") or "unknown"
            model = kwargs.get("model") or "unknown"
            base_url = kwargs.get("base_url")
            status = kwargs.get("status") or "unknown"
            started_at = kwargs.get("started_at")
            ended_at = kwargs.get("ended_at")
            duration_ms = None
            if started_at and ended_at:
                duration_ms = int((ended_at - started_at).total_seconds() * 1000)

            request_payload = kwargs.get("request_payload")
            response_payload = kwargs.get("response_payload")
            req_masked = mask_json(request_payload) if request_payload is not None else None
            resp_masked = mask_json(response_payload) if response_payload is not None else None

            event_data = {
                "id": str(uuid.uuid4()),
                "call_id": kwargs.get("call_id") or str(uuid.uuid4()),
                "provider": provider,
                "model": model,
                "base_url": mask_url(base_url) if base_url else None,
                "status": status,
                "started_at": started_at or datetime.now(UTC),
                "ended_at": ended_at,
                "duration_ms": duration_ms,
                "request_payload_masked": req_masked,
                "response_payload_masked": resp_masked,
                "request_readable": to_readable_request(req_masked if isinstance(req_masked, dict) else None),
                "response_readable": to_readable_response(resp_masked if isinstance(resp_masked, dict) else None),
                "prompt_tokens": kwargs.get("prompt_tokens"),
                "completion_tokens": kwargs.get("completion_tokens"),
                "total_tokens": kwargs.get("total_tokens"),
                "error_type": kwargs.get("error_type"),
                "error_message_masked": mask_text(kwargs.get("error_message")) if kwargs.get("error_message") else None,
                **payload,
            }

            if self._session_maker is not None:
                from app.application.llm_trace.repository import LLMTraceEventRepository

                async with self._session_maker() as session:
                    repo = LLMTraceEventRepository(session)
                    await repo.create_event(event_data)
        except Exception:
            logger.warning("LLMTraceRecorder._persist failed", exc_info=True)
