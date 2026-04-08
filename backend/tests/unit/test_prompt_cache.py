"""Unit tests for PromptCache."""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock

from app.infra.cache.prompt_cache import PromptCache
from app.domain.entities import Prompt


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    return AsyncMock()


@pytest.fixture
def sample_prompt():
    """Create sample prompt."""
    return Prompt(
        id="test-id",
        key="test_prompt",
        name="Test Prompt",
        description="A test prompt",
        category="test",
        content="Test content",
        variables=[],
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        current_version=1,
    )


@pytest.mark.asyncio
async def test_load_all(mock_repository, sample_prompt):
    """Test loading all prompts into cache."""
    mock_repository.list_all.return_value = [sample_prompt]

    cache = PromptCache()
    cache.set_repository(mock_repository)
    await cache.load_all()

    result = await cache.get("test_prompt")
    assert result == sample_prompt


@pytest.mark.asyncio
async def test_load_all_no_repository():
    """Test loading all prompts without repository raises error."""
    cache = PromptCache()

    with pytest.raises(RuntimeError, match="Repository not set"):
        await cache.load_all()


@pytest.mark.asyncio
async def test_get_from_cache(mock_repository, sample_prompt):
    """Test getting prompt from cache."""
    mock_repository.list_all.return_value = [sample_prompt]

    cache = PromptCache()
    cache.set_repository(mock_repository)
    await cache.load_all()

    result = await cache.get("test_prompt")
    assert result == sample_prompt
    # Should not call repository get_by_key since it's already cached
    mock_repository.get_by_key.assert_not_called()


@pytest.mark.asyncio
async def test_get_cache_miss(mock_repository, sample_prompt):
    """Test cache miss loads from repository."""
    mock_repository.get_by_key.return_value = sample_prompt

    cache = PromptCache()
    cache.set_repository(mock_repository)

    result = await cache.get("test_prompt")
    assert result == sample_prompt
    mock_repository.get_by_key.assert_called_once_with("test_prompt")


@pytest.mark.asyncio
async def test_get_cache_miss_not_found(mock_repository):
    """Test cache miss when prompt doesn't exist."""
    mock_repository.get_by_key.return_value = None

    cache = PromptCache()
    cache.set_repository(mock_repository)

    result = await cache.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_inactive_prompt(mock_repository):
    """Test that inactive prompts are not cached on miss."""
    inactive_prompt = Prompt(
        id="test-id",
        key="inactive_prompt",
        name="Inactive Prompt",
        description="An inactive prompt",
        category="test",
        content="Test content",
        variables=[],
        is_active=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        current_version=1,
    )
    mock_repository.get_by_key.return_value = inactive_prompt

    cache = PromptCache()
    cache.set_repository(mock_repository)

    result = await cache.get("inactive_prompt")
    assert result is None


@pytest.mark.asyncio
async def test_get_no_repository():
    """Test getting prompt without repository returns None."""
    cache = PromptCache()

    result = await cache.get("test_prompt")
    assert result is None


def test_refresh(sample_prompt):
    """Test refreshing prompt in cache."""
    cache = PromptCache()
    cache.refresh(sample_prompt)

    result = cache.get_all_keys()
    assert "test_prompt" in result


def test_refresh_inactive_prompt():
    """Test refreshing inactive prompt removes it from cache."""
    cache = PromptCache()

    # First add an active prompt
    active_prompt = Prompt(
        id="test-id",
        key="test_prompt",
        name="Test Prompt",
        description="A test prompt",
        category="test",
        content="Test content",
        variables=[],
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        current_version=1,
    )
    cache.refresh(active_prompt)
    assert "test_prompt" in cache.get_all_keys()

    # Now mark it as inactive
    inactive_prompt = Prompt(
        id="test-id",
        key="test_prompt",
        name="Test Prompt",
        description="A test prompt",
        category="test",
        content="Test content",
        variables=[],
        is_active=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        current_version=1,
    )
    cache.refresh(inactive_prompt)

    keys = cache.get_all_keys()
    assert "test_prompt" not in keys


def test_invalidate(sample_prompt):
    """Test invalidating prompt from cache."""
    cache = PromptCache()
    cache.refresh(sample_prompt)

    cache.invalidate("test_prompt")

    # Cache should be empty
    keys = cache.get_all_keys()
    assert "test_prompt" not in keys


def test_invalidate_nonexistent_key():
    """Test invalidating a key that doesn't exist."""
    cache = PromptCache()

    # Should not raise an error
    cache.invalidate("nonexistent")

    keys = cache.get_all_keys()
    assert len(keys) == 0


def test_clear(sample_prompt):
    """Test clearing all prompts from cache."""
    cache = PromptCache()
    cache.refresh(sample_prompt)

    cache.clear()

    keys = cache.get_all_keys()
    assert len(keys) == 0


def test_get_all_keys(sample_prompt):
    """Test getting all cached keys."""
    another_prompt = Prompt(
        id="another-id",
        key="another_prompt",
        name="Another Prompt",
        description="Another test prompt",
        category="test",
        content="Another content",
        variables=[],
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        current_version=1,
    )

    cache = PromptCache()
    cache.refresh(sample_prompt)
    cache.refresh(another_prompt)

    keys = cache.get_all_keys()
    assert len(keys) == 2
    assert "test_prompt" in keys
    assert "another_prompt" in keys


def test_set_repository():
    """Test setting repository."""
    cache = PromptCache()
    mock_repo = AsyncMock()

    cache.set_repository(mock_repo)

    assert cache._repository == mock_repo


@pytest.mark.asyncio
async def test_multiple_prompts_cached(mock_repository):
    """Test caching multiple prompts."""
    prompt1 = Prompt(
        id="id1",
        key="prompt1",
        name="Prompt 1",
        description="First prompt",
        category="test",
        content="Content 1",
        variables=[],
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        current_version=1,
    )
    prompt2 = Prompt(
        id="id2",
        key="prompt2",
        name="Prompt 2",
        description="Second prompt",
        category="test",
        content="Content 2",
        variables=[],
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        current_version=1,
    )

    mock_repository.list_all.return_value = [prompt1, prompt2]

    cache = PromptCache()
    cache.set_repository(mock_repository)
    await cache.load_all()

    result1 = await cache.get("prompt1")
    result2 = await cache.get("prompt2")

    assert result1.key == "prompt1"
    assert result2.key == "prompt2"
