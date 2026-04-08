"""Unit tests for PromptService."""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock

from app.application.prompt_service import PromptService
from app.domain.entities import Prompt
from app.domain.exceptions import PromptNotFoundError, PromptVariableError


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    return AsyncMock()


@pytest.fixture
def mock_cache():
    """Create mock cache."""
    cache = MagicMock()
    cache.get = AsyncMock()
    cache.refresh = MagicMock()
    return cache


@pytest.fixture
def sample_prompt():
    """Create sample prompt."""
    return Prompt(
        id="test-id",
        key="test_prompt",
        name="Test Prompt",
        description="A test prompt",
        category="test",
        content="Hello {name}!",
        variables=[{"name": "name", "description": "User name"}],
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        current_version=1,
    )


@pytest.mark.asyncio
async def test_get_prompt_from_cache(mock_repository, mock_cache, sample_prompt):
    """Test getting prompt from cache."""
    mock_cache.get.return_value = sample_prompt

    service = PromptService(mock_repository, mock_cache)
    result = await service.get_prompt("test_prompt")

    assert result.key == "test_prompt"
    mock_cache.get.assert_called_once_with("test_prompt")


@pytest.mark.asyncio
async def test_get_prompt_not_found(mock_repository, mock_cache):
    """Test getting non-existent prompt."""
    mock_cache.get.return_value = None

    service = PromptService(mock_repository, mock_cache)
    result = await service.get_prompt("nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_render_prompt(mock_repository, mock_cache, sample_prompt):
    """Test rendering prompt with variables."""
    mock_cache.get.return_value = sample_prompt

    service = PromptService(mock_repository, mock_cache)
    result = await service.render_prompt("test_prompt", {"name": "World"})

    assert result == "Hello World!"


@pytest.mark.asyncio
async def test_render_prompt_missing_variable(mock_repository, mock_cache, sample_prompt):
    """Test rendering prompt with missing variable."""
    mock_cache.get.return_value = sample_prompt

    service = PromptService(mock_repository, mock_cache)

    with pytest.raises(PromptVariableError):
        await service.render_prompt("test_prompt", {})


@pytest.mark.asyncio
async def test_render_prompt_not_found(mock_repository, mock_cache):
    """Test rendering non-existent prompt."""
    mock_cache.get.return_value = None

    service = PromptService(mock_repository, mock_cache)
    result = await service.render_prompt("nonexistent", {})

    assert result is None


@pytest.mark.asyncio
async def test_list_prompts(mock_repository, mock_cache, sample_prompt):
    """Test listing prompts."""
    mock_repository.list_all.return_value = [sample_prompt]

    service = PromptService(mock_repository, mock_cache)
    result = await service.list_prompts()

    assert len(result) == 1
    assert result[0].key == "test_prompt"
    mock_repository.list_all.assert_called_once_with(
        category=None,
        include_inactive=False,
    )


@pytest.mark.asyncio
async def test_list_prompts_with_category(mock_repository, mock_cache, sample_prompt):
    """Test listing prompts filtered by category."""
    mock_repository.list_all.return_value = [sample_prompt]

    service = PromptService(mock_repository, mock_cache)
    result = await service.list_prompts(category="test")

    assert len(result) == 1
    mock_repository.list_all.assert_called_once_with(
        category="test",
        include_inactive=False,
    )


@pytest.mark.asyncio
async def test_update_prompt(mock_repository, mock_cache, sample_prompt):
    """Test updating prompt."""
    updated_prompt = Prompt(
        id="test-id",
        key="test_prompt",
        name="Test Prompt",
        description="A test prompt",
        category="test",
        content="New content",
        variables=[],
        is_active=True,
        created_at=sample_prompt.created_at,
        updated_at=datetime.now(UTC),
        current_version=2,
    )
    mock_repository.update.return_value = updated_prompt

    service = PromptService(mock_repository, mock_cache)
    result = await service.update_prompt(
        "test_prompt",
        "New content",
        changed_by="admin",
        change_reason="Update test",
    )

    assert result.content == "New content"
    assert result.current_version == 2
    mock_repository.update.assert_called_once()
    mock_cache.refresh.assert_called_once_with(updated_prompt)


@pytest.mark.asyncio
async def test_create_prompt(mock_repository, mock_cache, sample_prompt):
    """Test creating prompt."""
    mock_repository.create.return_value = sample_prompt

    service = PromptService(mock_repository, mock_cache)
    result = await service.create_prompt(
        key="test_prompt",
        name="Test Prompt",
        category="test",
        content="Hello {name}!",
        description="A test prompt",
        variables=[{"name": "name", "description": "User name"}],
    )

    assert result.key == "test_prompt"
    mock_repository.create.assert_called_once()
    mock_cache.refresh.assert_called_once_with(sample_prompt)


@pytest.mark.asyncio
async def test_get_version(mock_repository, mock_cache):
    """Test getting specific version."""
    from app.domain.entities import PromptVersion

    version = PromptVersion(
        id="version-id",
        prompt_id="test-id",
        version=1,
        content="Original content",
        changed_by="admin",
        change_reason="Initial",
        created_at=datetime.now(UTC),
    )
    mock_repository.get_version.return_value = version

    service = PromptService(mock_repository, mock_cache)
    result = await service.get_version("test_prompt", 1)

    assert result.version == 1
    mock_repository.get_version.assert_called_once_with("test_prompt", 1)


@pytest.mark.asyncio
async def test_list_versions(mock_repository, mock_cache):
    """Test listing versions."""
    from app.domain.entities import PromptVersion

    versions = [
        PromptVersion(
            id="v1",
            prompt_id="test-id",
            version=1,
            content="Version 1",
            changed_by="admin",
            change_reason="Initial",
            created_at=datetime.now(UTC),
        ),
        PromptVersion(
            id="v2",
            prompt_id="test-id",
            version=2,
            content="Version 2",
            changed_by="admin",
            change_reason="Update",
            created_at=datetime.now(UTC),
        ),
    ]
    mock_repository.list_versions.return_value = versions
    mock_repository.count_versions.return_value = 2

    service = PromptService(mock_repository, mock_cache)
    result, total = await service.list_versions("test_prompt", skip=0, limit=20)

    assert len(result) == 2
    assert total == 2


@pytest.mark.asyncio
async def test_rollback_to_version(mock_repository, mock_cache, sample_prompt):
    """Test rolling back to a specific version."""
    mock_repository.rollback_to_version.return_value = sample_prompt

    service = PromptService(mock_repository, mock_cache)
    result = await service.rollback_to_version("test_prompt", 1, changed_by="admin")

    assert result.key == "test_prompt"
    mock_repository.rollback_to_version.assert_called_once()
    mock_cache.refresh.assert_called_once_with(sample_prompt)


@pytest.mark.asyncio
async def test_reload_cache_single_prompt(mock_repository, mock_cache, sample_prompt):
    """Test reloading a single prompt into cache."""
    mock_repository.get_by_key.return_value = sample_prompt

    service = PromptService(mock_repository, mock_cache)
    await service.reload_cache("test_prompt")

    mock_repository.get_by_key.assert_called_once_with("test_prompt")
    mock_cache.refresh.assert_called_once_with(sample_prompt)


@pytest.mark.asyncio
async def test_reload_cache_prompt_not_found(mock_repository, mock_cache):
    """Test reloading a prompt that doesn't exist."""
    mock_repository.get_by_key.return_value = None

    service = PromptService(mock_repository, mock_cache)
    await service.reload_cache("nonexistent")

    mock_cache.invalidate.assert_called_once_with("nonexistent")


@pytest.mark.asyncio
async def test_reload_cache_all(mock_repository, mock_cache):
    """Test reloading all prompts into cache."""
    mock_cache.load_all = AsyncMock()

    service = PromptService(mock_repository, mock_cache)
    await service.reload_cache()

    mock_cache.load_all.assert_called_once()
