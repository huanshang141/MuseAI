# backend/app/application/document_service.py
"""Document service with dependency on repository port.

This service implements document business logic without depending
on infrastructure layer modules at the module level. It uses repository
ports (protocols) that are implemented by adapters in the infrastructure layer.
"""

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from app.infra.postgres.models import Document, IngestionJob


SANITIZED_ERROR_MESSAGE = "processing_failed"


def sanitize_error_message(error: str | None) -> str | None:
    """Sanitize error messages to prevent internal exception leakage.

    Raw exception messages can contain sensitive information like:
    - Internal file paths
    - Stack traces
    - Connection URLs
    - API keys or secrets
    - Internal hostnames

    This function returns a sanitized generic message instead of the raw error.

    Args:
        error: The raw error message to sanitize.

    Returns:
        A sanitized error message safe for storage and potential exposure.
    """
    if error is None:
        return None
    logger.error(f"Document service error (sanitized): {error}")
    return SANITIZED_ERROR_MESSAGE


async def create_document(
    doc_repo: "DocumentRepositoryPort", filename: str, user_id: str
) -> "Document":
    """Create a new document with associated ingestion job.

    Args:
        doc_repo: Repository implementing DocumentRepositoryPort.
        filename: Name of the uploaded file.
        user_id: ID of the user uploading the file.

    Returns:
        The newly created Document instance.
    """
    document, _ = await doc_repo.create(filename, user_id)
    return document


async def get_documents_by_user(
    doc_repo: "DocumentRepositoryPort",
    user_id: str,
    limit: int = 20,
    offset: int = 0,
) -> list["Document"]:
    """Get documents for a user with pagination.

    Args:
        doc_repo: Repository implementing DocumentRepositoryPort.
        user_id: User ID to filter by.
        limit: Maximum number of documents to return.
        offset: Number of documents to skip.

    Returns:
        List of Document instances.
    """
    return await doc_repo.get_by_user_id(user_id, limit=limit, offset=offset)


async def count_documents_by_user(doc_repo: "DocumentRepositoryPort", user_id: str) -> int:
    """Count total documents for a user.

    Args:
        doc_repo: Repository implementing DocumentRepositoryPort.
        user_id: User ID to count documents for.

    Returns:
        Total document count for the user.
    """
    return await doc_repo.count_by_user_id(user_id)


async def get_document_by_id(
    doc_repo: "DocumentRepositoryPort", doc_id: str, user_id: str
) -> "Document | None":
    """Get a document by ID, filtered by user ownership.

    Args:
        doc_repo: Repository implementing DocumentRepositoryPort.
        doc_id: Document ID to retrieve.
        user_id: User ID that must own the document.

    Returns:
        Document if found and owned by user, None otherwise.
    """
    document = await doc_repo.get_by_id(doc_id)
    if document is not None and document.user_id == user_id:
        return document
    return None


async def get_ingestion_job_by_document(
    doc_repo: "DocumentRepositoryPort", doc_id: str
) -> "IngestionJob | None":
    """Get ingestion job for a document.

    Args:
        doc_repo: Repository implementing DocumentRepositoryPort.
        doc_id: Document ID to get ingestion job for.

    Returns:
        IngestionJob if found, None otherwise.
    """
    return await doc_repo.get_ingestion_job_by_document(doc_id)


async def delete_document(
    doc_repo: "DocumentRepositoryPort", doc_id: str, user_id: str
) -> bool:
    """Delete a document by ID, filtered by user ownership.

    Args:
        doc_repo: Repository implementing DocumentRepositoryPort.
        doc_id: Document ID to delete.
        user_id: User ID that must own the document.

    Returns:
        True if deleted, False if not found or not owned.
    """
    document = await doc_repo.get_by_id(doc_id)
    if document is None or document.user_id != user_id:
        return False
    return await doc_repo.delete(doc_id)


async def update_document_status(
    doc_repo: "DocumentRepositoryPort",
    doc_id: str,
    status: str,
    error: str | None = None,
    chunk_count: int | None = None,
) -> "Document | None":
    """Update document status and optionally set error message.

    Also updates the associated IngestionJob if chunk_count is provided.

    Args:
        doc_repo: Repository implementing DocumentRepositoryPort.
        doc_id: Document ID to update.
        status: New status value.
        error: Optional error message (will be sanitized before storage).
        chunk_count: Optional chunk count for ingestion job.

    Returns:
        Updated Document instance, or None if not found.
    """
    # Sanitize error message to prevent internal exception leakage
    sanitized_error = sanitize_error_message(error)
    return await doc_repo.update_status(doc_id, status, sanitized_error, chunk_count)


async def get_all_documents(
    doc_repo: "DocumentRepositoryPort", limit: int = 20, offset: int = 0
) -> list["Document"]:
    """Get all documents with pagination (admin access).

    Args:
        doc_repo: Repository implementing DocumentRepositoryPort.
        limit: Maximum number of documents to return.
        offset: Number of documents to skip.

    Returns:
        List of Document instances.
    """
    return await doc_repo.get_all(limit=limit, offset=offset)


async def count_all_documents(doc_repo: "DocumentRepositoryPort") -> int:
    """Count total documents across all users (admin access).

    Args:
        doc_repo: Repository implementing DocumentRepositoryPort.

    Returns:
        Total document count.
    """
    return await doc_repo.count_all()


async def get_document_by_id_public(
    doc_repo: "DocumentRepositoryPort", doc_id: str
) -> "Document | None":
    """Get document by ID without user filtering (admin access).

    Args:
        doc_repo: Repository implementing DocumentRepositoryPort.
        doc_id: Document ID to retrieve.

    Returns:
        Document if found, None otherwise.
    """
    return await doc_repo.get_by_id(doc_id)


async def delete_document_by_id(
    doc_repo: "DocumentRepositoryPort", doc_id: str
) -> bool:
    """Delete document by ID without user filtering (admin access).

    Args:
        doc_repo: Repository implementing DocumentRepositoryPort.
        doc_id: Document ID to delete.

    Returns:
        True if deleted, False if not found.
    """
    return await doc_repo.delete(doc_id)


# Import the protocol for type hints
from app.application.ports.repositories import DocumentRepositoryPort  # noqa: E402

__all__ = [
    "create_document",
    "get_documents_by_user",
    "count_documents_by_user",
    "get_document_by_id",
    "get_ingestion_job_by_document",
    "delete_document",
    "update_document_status",
    "get_all_documents",
    "count_all_documents",
    "get_document_by_id_public",
    "delete_document_by_id",
    "DocumentRepositoryPort",
    "sanitize_error_message",
    "SANITIZED_ERROR_MESSAGE",
]
