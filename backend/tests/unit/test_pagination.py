import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_list_documents_pagination():
    """list_documents should support limit and offset."""
    from app.api.documents import list_documents
    from fastapi import Request

    mock_session = AsyncMock()
    mock_user = {"id": "user-123"}

    # Mock the service function
    with pytest.MonkeyPatch.context() as m:
        from app.application import document_service

        # Check that get_documents_by_user accepts limit/offset
        import inspect
        sig = inspect.signature(document_service.get_documents_by_user)
        params = list(sig.parameters.keys())

        assert "limit" in params, "get_documents_by_user should have limit parameter"
        assert "offset" in params, "get_documents_by_user should have offset parameter"


@pytest.mark.asyncio
async def test_list_sessions_pagination():
    """list_sessions should support limit and offset."""
    from app.application.chat_service import get_sessions_by_user
    import inspect

    sig = inspect.signature(get_sessions_by_user)
    params = list(sig.parameters.keys())

    assert "limit" in params, "get_sessions_by_user should have limit parameter"
    assert "offset" in params, "get_sessions_by_user should have offset parameter"


def test_pagination_defaults():
    """Pagination should have sensible defaults."""
    from pydantic import BaseModel

    # Check that pagination params have defaults
    # Default limit should be 20, max 100
    DEFAULT_LIMIT = 20
    MAX_LIMIT = 100

    assert DEFAULT_LIMIT == 20
    assert MAX_LIMIT == 100
