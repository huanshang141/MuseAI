"""Tests for document_service module."""

from unittest.mock import AsyncMock, MagicMock

import pytest


def create_mock_doc_repo():
    """Create a mock document repository for testing."""
    mock_repo = MagicMock()
    mock_repo.create = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)
    mock_repo.get_by_user_id = AsyncMock(return_value=[])
    mock_repo.get_all = AsyncMock(return_value=[])
    mock_repo.count_all = AsyncMock(return_value=0)
    mock_repo.count_by_user_id = AsyncMock(return_value=0)
    mock_repo.update_status = AsyncMock(return_value=None)
    mock_repo.delete = AsyncMock(return_value=False)
    mock_repo.get_ingestion_job_by_document = AsyncMock(return_value=None)
    return mock_repo


class TestCreateDocument:
    """Tests for create_document function."""

    @pytest.mark.asyncio
    async def test_creates_document_and_ingestion_job(self):
        """create_document should create document and associated ingestion job."""
        from app.application.document_service import create_document

        mock_doc = MagicMock()
        mock_doc.id = "doc-123"
        mock_doc.filename = "test.pdf"

        mock_job = MagicMock()
        mock_job.id = "job-123"

        mock_repo = create_mock_doc_repo()
        mock_repo.create = AsyncMock(return_value=(mock_doc, mock_job))

        result = await create_document(
            doc_repo=mock_repo,
            filename="test.pdf",
            user_id="user-123",
        )

        assert result.id == "doc-123"
        mock_repo.create.assert_called_once_with("test.pdf", "user-123")


class TestGetDocumentsByUser:
    """Tests for get_documents_by_user function."""

    @pytest.mark.asyncio
    async def test_returns_list_of_documents(self):
        """get_documents_by_user should return list of user's documents."""
        from app.application.document_service import get_documents_by_user

        mock_document = MagicMock()
        mock_document.id = "doc-123"
        mock_document.filename = "test.pdf"

        mock_repo = create_mock_doc_repo()
        mock_repo.get_by_user_id = AsyncMock(return_value=[mock_document])

        result = await get_documents_by_user(mock_repo, "user-123")

        assert len(result) == 1
        assert result[0].id == "doc-123"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_documents(self):
        """get_documents_by_user should return empty list when no documents."""
        from app.application.document_service import get_documents_by_user

        mock_repo = create_mock_doc_repo()
        mock_repo.get_by_user_id = AsyncMock(return_value=[])

        result = await get_documents_by_user(mock_repo, "user-123")

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

        mock_repo = create_mock_doc_repo()
        mock_repo.get_by_id = AsyncMock(return_value=mock_document)

        result = await get_document_by_id(mock_repo, "doc-123", "user-123")

        assert result.id == "doc-123"

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(self):
        """get_document_by_id should return None if document not found."""
        from app.application.document_service import get_document_by_id

        mock_repo = create_mock_doc_repo()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        result = await get_document_by_id(mock_repo, "nonexistent", "user-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_if_not_owner(self):
        """get_document_by_id should return None if not owned by user."""
        from app.application.document_service import get_document_by_id

        mock_document = MagicMock()
        mock_document.id = "doc-123"
        mock_document.user_id = "different-user"

        mock_repo = create_mock_doc_repo()
        mock_repo.get_by_id = AsyncMock(return_value=mock_document)

        result = await get_document_by_id(mock_repo, "doc-123", "user-123")

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

        mock_repo = create_mock_doc_repo()
        mock_repo.get_ingestion_job_by_document = AsyncMock(return_value=mock_job)

        result = await get_ingestion_job_by_document(mock_repo, "doc-123")

        assert result.id == "job-123"

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(self):
        """get_ingestion_job_by_document should return None if not found."""
        from app.application.document_service import get_ingestion_job_by_document

        mock_repo = create_mock_doc_repo()
        mock_repo.get_ingestion_job_by_document = AsyncMock(return_value=None)

        result = await get_ingestion_job_by_document(mock_repo, "nonexistent")

        assert result is None


class TestDeleteDocument:
    """Tests for delete_document function."""

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        """delete_document should return True when document deleted."""
        from app.application.document_service import delete_document

        mock_document = MagicMock()
        mock_document.id = "doc-123"
        mock_document.user_id = "user-123"

        mock_repo = create_mock_doc_repo()
        mock_repo.get_by_id = AsyncMock(return_value=mock_document)
        mock_repo.delete = AsyncMock(return_value=True)

        result = await delete_document(mock_repo, "doc-123", "user-123")

        assert result is True
        mock_repo.delete.assert_called_once_with("doc-123")

    @pytest.mark.asyncio
    async def test_returns_false_if_not_found(self):
        """delete_document should return False if document not found."""
        from app.application.document_service import delete_document

        mock_repo = create_mock_doc_repo()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        result = await delete_document(mock_repo, "nonexistent", "user-123")

        assert result is False
        mock_repo.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_if_not_owner(self):
        """delete_document should return False if user is not owner."""
        from app.application.document_service import delete_document

        mock_document = MagicMock()
        mock_document.id = "doc-123"
        mock_document.user_id = "different-user"

        mock_repo = create_mock_doc_repo()
        mock_repo.get_by_id = AsyncMock(return_value=mock_document)

        result = await delete_document(mock_repo, "doc-123", "user-123")

        assert result is False
        mock_repo.delete.assert_not_called()


class TestUpdateDocumentStatus:
    """Tests for update_document_status function."""

    @pytest.mark.asyncio
    async def test_updates_status_and_error(self):
        """update_document_status should update status and sanitize error."""
        from app.application.document_service import (
            SANITIZED_ERROR_MESSAGE,
            update_document_status,
        )

        mock_document = MagicMock()
        mock_document.id = "doc-123"
        mock_document.status = "pending"
        mock_document.error = None

        mock_repo = create_mock_doc_repo()
        mock_repo.update_status = AsyncMock(return_value=mock_document)

        result = await update_document_status(
            mock_repo,
            "doc-123",
            "failed",
            "Processing error",
        )

        # Error should be sanitized to prevent internal exception leakage
        mock_repo.update_status.assert_called_once_with("doc-123", "failed", SANITIZED_ERROR_MESSAGE, None)
        assert result == mock_document

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(self):
        """update_document_status should return None if document not found."""
        from app.application.document_service import update_document_status

        mock_repo = create_mock_doc_repo()
        mock_repo.update_status = AsyncMock(return_value=None)

        result = await update_document_status(
            mock_repo,
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

        mock_repo = create_mock_doc_repo()
        mock_repo.update_status = AsyncMock(return_value=mock_document)

        await update_document_status(
            mock_repo,
            "doc-123",
            "completed",
            None,
        )

        mock_repo.update_status.assert_called_once_with("doc-123", "completed", None, None)


class TestGetAllDocuments:
    """Tests for get_all_documents function."""

    @pytest.mark.asyncio
    async def test_returns_list_of_all_documents(self):
        """get_all_documents should return list of all documents."""
        from app.application.document_service import get_all_documents

        mock_document1 = MagicMock()
        mock_document1.id = "doc-1"
        mock_document1.filename = "test1.pdf"
        mock_document1.user_id = "user-123"

        mock_document2 = MagicMock()
        mock_document2.id = "doc-2"
        mock_document2.filename = "test2.pdf"
        mock_document2.user_id = "user-456"

        mock_repo = create_mock_doc_repo()
        mock_repo.get_all = AsyncMock(return_value=[mock_document1, mock_document2])

        result = await get_all_documents(mock_repo)

        assert len(result) == 2
        assert result[0].id == "doc-1"
        assert result[1].id == "doc-2"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_documents(self):
        """get_all_documents should return empty list when no documents exist."""
        from app.application.document_service import get_all_documents

        mock_repo = create_mock_doc_repo()
        mock_repo.get_all = AsyncMock(return_value=[])

        result = await get_all_documents(mock_repo)

        assert result == []

    @pytest.mark.asyncio
    async def test_respects_limit_and_offset(self):
        """get_all_documents should respect pagination parameters."""
        from app.application.document_service import get_all_documents

        mock_document = MagicMock()
        mock_repo = create_mock_doc_repo()
        mock_repo.get_all = AsyncMock(return_value=[mock_document])

        result = await get_all_documents(mock_repo, limit=5, offset=10)

        assert len(result) == 1
        mock_repo.get_all.assert_called_once_with(limit=5, offset=10)


class TestCountAllDocuments:
    """Tests for count_all_documents function."""

    @pytest.mark.asyncio
    async def test_returns_total_count(self):
        """count_all_documents should return total document count."""
        from app.application.document_service import count_all_documents

        mock_repo = create_mock_doc_repo()
        mock_repo.count_all = AsyncMock(return_value=42)

        result = await count_all_documents(mock_repo)

        assert result == 42

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_documents(self):
        """count_all_documents should return 0 when no documents exist."""
        from app.application.document_service import count_all_documents

        mock_repo = create_mock_doc_repo()
        mock_repo.count_all = AsyncMock(return_value=0)

        result = await count_all_documents(mock_repo)

        assert result == 0


class TestGetDocumentByIdPublic:
    """Tests for get_document_by_id_public function."""

    @pytest.mark.asyncio
    async def test_returns_document_without_user_check(self):
        """get_document_by_id_public should return document without user check."""
        from app.application.document_service import get_document_by_id_public

        mock_document = MagicMock()
        mock_document.id = "doc-123"
        mock_document.user_id = "user-456"

        mock_repo = create_mock_doc_repo()
        mock_repo.get_by_id = AsyncMock(return_value=mock_document)

        result = await get_document_by_id_public(mock_repo, "doc-123")

        assert result.id == "doc-123"
        assert result.user_id == "user-456"

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(self):
        """get_document_by_id_public should return None if document not found."""
        from app.application.document_service import get_document_by_id_public

        mock_repo = create_mock_doc_repo()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        result = await get_document_by_id_public(mock_repo, "nonexistent")

        assert result is None


class TestDeleteDocumentById:
    """Tests for delete_document_by_id function."""

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        """delete_document_by_id should return True when document deleted."""
        from app.application.document_service import delete_document_by_id

        mock_repo = create_mock_doc_repo()
        mock_repo.delete = AsyncMock(return_value=True)

        result = await delete_document_by_id(mock_repo, "doc-123")

        assert result is True
        mock_repo.delete.assert_called_once_with("doc-123")

    @pytest.mark.asyncio
    async def test_returns_false_if_not_found(self):
        """delete_document_by_id should return False if document not found."""
        from app.application.document_service import delete_document_by_id

        mock_repo = create_mock_doc_repo()
        mock_repo.delete = AsyncMock(return_value=False)

        result = await delete_document_by_id(mock_repo, "nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_deletes_without_user_check(self):
        """delete_document_by_id should delete document regardless of user."""
        from app.application.document_service import delete_document_by_id

        mock_repo = create_mock_doc_repo()
        mock_repo.delete = AsyncMock(return_value=True)

        result = await delete_document_by_id(mock_repo, "doc-123")

        assert result is True
        mock_repo.delete.assert_called_once_with("doc-123")


class TestCountDocumentsByUser:
    """Tests for count_documents_by_user function."""

    @pytest.mark.asyncio
    async def test_returns_count_for_user(self):
        """count_documents_by_user should return count for specific user."""
        from app.application.document_service import count_documents_by_user

        mock_repo = create_mock_doc_repo()
        mock_repo.count_by_user_id = AsyncMock(return_value=5)

        result = await count_documents_by_user(mock_repo, "user-123")

        assert result == 5
        mock_repo.count_by_user_id.assert_called_once_with("user-123")

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_documents(self):
        """count_documents_by_user should return 0 when user has no documents."""
        from app.application.document_service import count_documents_by_user

        mock_repo = create_mock_doc_repo()
        mock_repo.count_by_user_id = AsyncMock(return_value=0)

        result = await count_documents_by_user(mock_repo, "user-123")

        assert result == 0
