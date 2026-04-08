"""Exhibit indexing service for RAG retrieval."""

import asyncio
import warnings
from typing import Any

from loguru import logger

warnings.warn(
    "ExhibitIndexingService is deprecated. Use UnifiedIndexingService instead.",
    DeprecationWarning,
    stacklevel=2,
)

from app.domain.entities import Exhibit
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain.embeddings import CustomOllamaEmbeddings


class ExhibitIndexingService:
    """Service for indexing exhibit information to Elasticsearch."""

    def __init__(
        self,
        es_client: ElasticsearchClient,
        embeddings: CustomOllamaEmbeddings,
    ):
        self.es_client = es_client
        self.embeddings = embeddings

    def _build_exhibit_text(self, exhibit: Exhibit) -> str:
        """Build searchable text from exhibit attributes.

        Args:
            exhibit: The exhibit entity to build text for.

        Returns:
            Combined text string for embedding and search.
        """
        parts = [
            exhibit.name,
            exhibit.description or "",
            exhibit.category or "",
            exhibit.era or "",
            exhibit.hall or "",
        ]
        return " ".join(part for part in parts if part)

    async def index_exhibit(self, exhibit: Exhibit) -> dict[str, Any]:
        """Index a single exhibit to Elasticsearch.

        Args:
            exhibit: The exhibit entity to index.

        Returns:
            Result from Elasticsearch indexing operation.
        """
        text = self._build_exhibit_text(exhibit)
        embedding = await self.embeddings.aembed_query(text)

        doc = {
            "doc_type": "exhibit",
            "exhibit_id": exhibit.id.value,
            "name": exhibit.name,
            "description": exhibit.description or "",
            "category": exhibit.category or "",
            "hall": exhibit.hall or "",
            "floor": exhibit.location.floor if exhibit.location else 1,
            "era": exhibit.era or "",
            "importance": exhibit.importance,
            "estimated_visit_time": exhibit.estimated_visit_time or 0,
            "content": text,
            "content_vector": embedding,
            "location_x": exhibit.location.x if exhibit.location else 0,
            "location_y": exhibit.location.y if exhibit.location else 0,
            "is_active": exhibit.is_active,
            "document_id": exhibit.document_id if exhibit.document_id else None,
        }

        result = await self.es_client.index_exhibit(doc)
        logger.info(f"Indexed exhibit: {exhibit.id.value}")
        return result

    async def delete_exhibit_index(self, exhibit_id: str) -> dict[str, Any]:
        """Remove an exhibit from the Elasticsearch index.

        Args:
            exhibit_id: The ID of the exhibit to delete.

        Returns:
            Result from Elasticsearch delete operation.
        """
        result = await self.es_client.delete_exhibit(exhibit_id)
        logger.info(f"Deleted exhibit index: {exhibit_id}")
        return result

    async def reindex_all_exhibits(
        self,
        exhibits: list[Exhibit],
        batch_size: int = 10,
    ) -> dict[str, Any]:
        """Reindex all exhibits in batches.

        Args:
            exhibits: List of exhibit entities to index.
            batch_size: Number of exhibits to process concurrently.

        Returns:
            Summary of indexing results with counts.
        """
        indexed_count = 0
        failed_count = 0
        errors: list[str] = []

        semaphore = asyncio.Semaphore(batch_size)

        async def index_with_semaphore(exhibit: Exhibit) -> tuple[bool, str | None]:
            async with semaphore:
                try:
                    await self.index_exhibit(exhibit)
                    return (True, None)
                except Exception as e:
                    error_msg = f"Failed to index exhibit {exhibit.id.value}: {e}"
                    logger.error(error_msg)
                    return (False, error_msg)

        results = await asyncio.gather(
            *[index_with_semaphore(exhibit) for exhibit in exhibits]
        )

        for success, error in results:
            if success:
                indexed_count += 1
            else:
                failed_count += 1
                if error:
                    errors.append(error)

        summary = {
            "total": len(exhibits),
            "indexed": indexed_count,
            "failed": failed_count,
            "errors": errors if errors else None,
        }

        logger.info(
            f"Reindex complete: {indexed_count} indexed, {failed_count} failed"
        )
        return summary
