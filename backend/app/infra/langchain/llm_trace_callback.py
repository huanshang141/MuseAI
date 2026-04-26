from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class LLMTraceCallbackHandler(AsyncCallbackHandler):
    def __init__(self, trace_recorder: Any | None = None, source: str = "langchain_llm") -> None:
        self.trace_recorder = trace_recorder
        self.source = source
        self._call_state: dict[str, dict[str, Any]] = {}

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        call_id = f"lc-{uuid.uuid4().hex[:12]}"
        self._call_state[str(run_id)] = {
            "call_id": call_id,
            "started_at": datetime.now(UTC),
            "prompts": prompts,
            "serialized": serialized,
        }

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        state = self._call_state.pop(str(run_id), None)
        if state is None:
            return
        if self.trace_recorder is None:
            return

        ended_at = datetime.now(UTC)
        llm_output = response.llm_output or {}
        model_name = llm_output.get("model_name") or "unknown"
        token_usage = llm_output.get("token_usage") or {}
        generations = response.generations
        choices: list[dict[str, Any]] = []
        for gen_list in generations:
            for gen in gen_list:
                choices.append({"text": gen.text})

        await self.trace_recorder.record_call_once(
            call_id=state["call_id"],
            provider="langchain-openai",
            model=model_name,
            status="success",
            source=self.source,
            request_payload={"prompts": state["prompts"]},
            response_payload={"choices": choices, "usage": token_usage},
            prompt_tokens=token_usage.get("prompt_tokens") if isinstance(token_usage, dict) else None,
            completion_tokens=token_usage.get("completion_tokens") if isinstance(token_usage, dict) else None,
            total_tokens=token_usage.get("total_tokens") if isinstance(token_usage, dict) else None,
            started_at=state["started_at"],
            ended_at=ended_at,
        )

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        state = self._call_state.pop(str(run_id), None)
        if state is None:
            return
        if self.trace_recorder is None:
            return

        ended_at = datetime.now(UTC)
        await self.trace_recorder.record_call_error(
            call_id=state["call_id"],
            error_type=type(error).__name__,
            error_message=str(error),
            source=self.source,
            started_at=state["started_at"],
            ended_at=ended_at,
        )
