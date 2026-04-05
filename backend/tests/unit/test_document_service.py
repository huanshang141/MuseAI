"""Tests for document_service module."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone


class TestCreateDocument:
    """Tests for create_document function."""

    @pytest.mark.asyncio
    async def test_creates_document_and_ingestion_job(self):
        """create_document should create document and associated ingestion job."""
        from app.application.document_service import create_document

        mock_session = AsyncMock()
        added_objects = []
        mock_session.add = lambda obj: added_objects.append(obj)
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await create_document(
            session=mock_session,
            filename="test.pdf",
            size=1024,
            user_id="user-123",
        )

        # Should have added document and ingestion job
        assert len(added_objects) == 2
        assert mock_session.flush.called
        assert mock_session.refresh.called


class TestGetDocumentsByUser:
    """Tests for get_documents_by_user function."""

    @pytest.mark.asyncio
    async def test_returns_list_of_documents(self):
        """get_documents_by_user should return list of user's documents."""
        from app.application.document_service import get_documents_by_user

        mock_document = MagicMock()
        mock_document.id = "doc-123"
        mock_document.filename = "test.pdf"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_document]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_documents_by_user(mock_session, "user-123")

        assert len(result) == 1
        assert result[0].id == "doc-123"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_documents(self):
        """get_documents_by_user should return empty list when no documents."""
        from app.application.document_service import get_documents_by_user

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_documents_by_user(mock_session, "user-123")

        assert result == []


class TestGetDocumentById:
    """Tests for get_document_by_id function."""

    @pytest.mark.asyncio
    async def test_returns_document_if_owned_by_user(self):
        """get_document_by_id should return document if owned by user."""
        from app.application.document_service import get_document_by_id

        mock_document = MagicMock()
        mock_document.id = "doc-123"
        mock_document.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_document_by_id(mock_session, "doc-123", "user-123")

        assert result.id == "doc-123"

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(self):
        """get_document_by_id should return None if document not found."""
        from app.application.document_service import get_document_by_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_document_by_id(mock_session, "nonexistent", "user-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_if_not_owner(self):
        """get_document_by_id should return None if not owned by user."""
        from app.application.document_service import get_document_by_id

        # Query filters by user_id, so returns None for different user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_document_by_id(mock_session, "doc-123", "different-user")

        assert result is None


class TestGetIngestionJobByDocument:
    """Tests for get_ingestion_job_by_document function."""

    @pytest.mark.asyncio
    async def test_returns_job_if_exists(self):
        """get_ingestion_job_by_document should return job if exists."""
        from app.application.document_service import get_ingestion_job_by_document

        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.document_id = "doc-123"
        mock_job.status = "completed"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_ingestion_job_by_document(mock_session, "doc-123")

        assert result.id == "job-123"

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(self):
        """get_ingestion_job_by_document should return None if not found."""
        from app.application.document_service import get_ingestion_job_by_document

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_ingestion_job_by_document(mock_session, "nonexistent")

        assert result is None


class TestDeleteDocument:
    """Tests for delete_document function."""

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        """delete_document should return True when document deleted."""
        from app.application.document_service import delete_document

        mock_document = MagicMock()
        mock_document.id = "doc-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        result = await delete_document(mock_session, "doc-123", "user-123")

        assert result is True
        mock_session.delete.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_if_not_found(self):
        """delete_document should return False if document not found."""
        from app.application.document_service import delete_document

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await delete_document(mock_session, "nonexistent", "user-123")

        assert result is False
        mock_session.delete.assert_not_called()


class TestUpdateDocumentStatus:
    """Tests for update_document_status function."""

    @pytest.mark.asyncio
    async def test_updates_status_and_error(self):
        """update_document_status should update status and error."""
        from app.application.document_service import update_document_status

        mock_document = MagicMock()
        mock_document.id = "doc-123"
        mock_document.status = "pending"
        mock_document.error = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await update_document_status(
            mock_session,
            "doc-123",
            "failed",
            "Processing error",
        )

        assert mock_document.status == "failed"
        assert mock_document.error == "Processing error"
        assert result == mock_document

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(self):
        """update_document_status should return None if document not found."""
        from app.application.document_service import update_document_status

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await update_document_status(
            mock_session,
            "nonexistent",
            "completed",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_clears_error_when_none(self):
        """update_document_status should clear error when None passed."""
        from app.application.document_service import update_document_status

        mock_document = MagicMock()
        mock_document.id = "doc-123"
        mock_document.status = "failed"
        mock_document.error = "Previous error"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await update_document_status(
            mock_session,
            "doc-123",
            "completed",
            None,
        )

        assert mock_document.status == "completed"
        assert mock_document.error is None
