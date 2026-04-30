"""Tests for PostgresPromptRepository.update_with_variables."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.domain.exceptions import PromptNotFoundError
from app.infra.postgres.adapters.prompt import PostgresPromptRepository


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def repo(mock_session):
    return PostgresPromptRepository(mock_session)


def _make_prompt_orm(prompt_id="p1", key="tour_tts_persona_a", variables=None):
    orm = MagicMock()
    orm.id = prompt_id
    orm.key = key
    orm.name = "Tour TTS - Archaeologist"
    orm.description = None
    orm.category = "tts"
    orm.content = "old content"
    orm.variables = variables or []
    orm.is_active = True
    orm.created_at = MagicMock(isoformat=MagicMock(return_value="2026-01-01T00:00:00"))
    orm.updated_at = MagicMock(isoformat=MagicMock(return_value="2026-01-01T00:00:00"))
    v = MagicMock()
    v.version = 1
    orm.versions = [v]
    return orm


class TestUpdateWithVariables:
    @pytest.mark.asyncio
    async def test_updates_content_and_variables(self, repo, mock_session):
        orm = _make_prompt_orm()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = orm
        mock_session.execute = AsyncMock(side_effect=[
            mock_result,  # get_by_key
            MagicMock(scalar=MagicMock(return_value=1)),  # max version
        ])

        new_vars = [{"name": "__voice_description__", "description": "test voice"}]
        result = await repo.update_with_variables(
            key="tour_tts_persona_a",
            content="new content",
            variables=new_vars,
            changed_by="admin@test.com",
            change_reason="test update",
        )

        assert orm.content == "new content"
        assert orm.variables == new_vars
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_new_version(self, repo, mock_session):
        orm = _make_prompt_orm()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = orm
        mock_session.execute = AsyncMock(side_effect=[
            mock_result,
            MagicMock(scalar=MagicMock(return_value=3)),
        ])

        await repo.update_with_variables(
            key="tour_tts_persona_a",
            content="content v4",
            variables=[],
        )

        version_orm = mock_session.add.call_args[0][0]
        assert version_orm.version == 4

    @pytest.mark.asyncio
    async def test_raises_when_not_found(self, repo, mock_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(PromptNotFoundError):
            await repo.update_with_variables(
                key="nonexistent",
                content="content",
                variables=[],
            )
