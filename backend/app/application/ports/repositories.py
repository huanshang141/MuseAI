# backend/app/application/ports/repositories.py
"""Repository port interfaces for hexagonal architecture.

These protocols define the contract that infrastructure adapters must implement.
The application layer depends on these ports, not on concrete implementations.
"""

from typing import Protocol


class UserRepositoryPort(Protocol):
    """Port interface for user repository operations."""

    async def get_by_email(self, email: str) -> "UserORM | None":
        """Retrieve a user by their email address.

        Args:
            email: The email address to search for.

        Returns:
            The user ORM instance if found, None otherwise.
        """
        ...

    async def get_by_id(self, user_id: str) -> "UserORM | None":
        """Retrieve a user by their unique identifier.

        Args:
            user_id: The unique identifier of the user.

        Returns:
            The user ORM instance if found, None otherwise.
        """
        ...

    async def add(self, user: "UserORM") -> None:
        """Add a new user to the repository.

        Args:
            user: The user ORM instance to add.
        """
        ...


class DocumentRepositoryPort(Protocol):
    """Port interface for document repository operations."""

    async def get_by_id(self, document_id: str) -> "DocumentORM | None":
        """Retrieve a document by its ID.

        Args:
            document_id: The unique identifier of the document.

        Returns:
            The document ORM instance if found, None otherwise.
        """
        ...

    async def get_by_user_id(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> list["DocumentORM"]:
        """Retrieve documents for a specific user with pagination.

        Args:
            user_id: The user ID to filter by.
            limit: Maximum number of documents to return.
            offset: Number of documents to skip.

        Returns:
            List of document ORM instances.
        """
        ...

    async def get_all(self, limit: int = 20, offset: int = 0) -> list["DocumentORM"]:
        """Retrieve all documents with pagination.

        Args:
            limit: Maximum number of documents to return.
            offset: Number of documents to skip.

        Returns:
            List of document ORM instances.
        """
        ...

    async def count_all(self) -> int:
        """Count total documents across all users.

        Returns:
            Total document count.
        """
        ...

    async def count_by_user_id(self, user_id: str) -> int:
        """Count documents for a specific user.

        Args:
            user_id: The user ID to count documents for.

        Returns:
            Document count for the user.
        """
        ...

    async def create(
        self, filename: str, user_id: str
    ) -> tuple["DocumentORM", "IngestionJobORM"]:
        """Create a new document with associated ingestion job.

        Args:
            filename: Name of the file.
            user_id: ID of the user creating the document.

        Returns:
            Tuple of (document, ingestion_job) ORM instances.
        """
        ...

    async def update_status(
        self,
        document_id: str,
        status: str,
        error: str | None = None,
        chunk_count: int | None = None,
    ) -> "DocumentORM | None":
        """Update document status and optionally error/chunk count.

        Args:
            document_id: ID of the document to update.
            status: New status value.
            error: Optional error message.
            chunk_count: Optional chunk count.

        Returns:
            Updated document ORM instance, or None if not found.
        """
        ...

    async def delete(self, document_id: str) -> bool:
        """Delete a document by ID.

        Args:
            document_id: ID of the document to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def get_ingestion_job_by_document(
        self, document_id: str
    ) -> "IngestionJobORM | None":
        """Get ingestion job for a document.

        Args:
            document_id: ID of the document.

        Returns:
            Ingestion job ORM instance, or None if not found.
        """
        ...


# Type aliases for ORM types (forward declarations for type hints)
# These are placeholders that will be satisfied by actual ORM types from adapters
UserORM = object  # type: ignore[misc]
DocumentORM = object  # type: ignore[misc]
IngestionJobORM = object  # type: ignore[misc]


__all__ = [
    "UserRepositoryPort",
    "DocumentRepositoryPort",
]
