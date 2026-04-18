"""Unit tests for the request_id ContextVar."""
import asyncio

import pytest


def test_request_id_var_default_is_none():
    from app.observability.context import request_id_var

    assert request_id_var.get() is None


def test_request_id_var_set_and_get():
    from app.observability.context import request_id_var

    token = request_id_var.set("req-123")
    try:
        assert request_id_var.get() == "req-123"
    finally:
        request_id_var.reset(token)

    assert request_id_var.get() is None


@pytest.mark.asyncio
async def test_request_id_var_isolated_across_concurrent_tasks():
    """ContextVar must give each asyncio task its own value — otherwise two
    concurrent requests would see each other's request_id."""
    from app.observability.context import request_id_var

    async def set_and_read(expected: str) -> str | None:
        token = request_id_var.set(expected)
        try:
            await asyncio.sleep(0)
            return request_id_var.get()
        finally:
            request_id_var.reset(token)

    results = await asyncio.gather(
        set_and_read("req-A"),
        set_and_read("req-B"),
        set_and_read("req-C"),
    )
    assert results == ["req-A", "req-B", "req-C"]


@pytest.mark.asyncio
async def test_request_id_var_propagates_into_child_task():
    """A child task spawned inside a request must inherit the parent's context."""
    from app.observability.context import request_id_var

    seen: list[str | None] = []

    async def child():
        seen.append(request_id_var.get())

    token = request_id_var.set("req-parent")
    try:
        await asyncio.create_task(child())
    finally:
        request_id_var.reset(token)

    assert seen == ["req-parent"]
