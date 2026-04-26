# backend/app/application/unified_indexing_service.py
"""Unified indexing service for all content types."""

import asyncio
from typing import Any

from loguru import logger

from app.application.chunking import ChunkConfig, TextChunker
from app.application.content_source import ContentSource
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain.embeddings import CustomOllamaEmbeddings


class UnifiedIndexingService:
    """Unified service for indexing any content source.

    Handles chunking, embedding, and indexing for both documents and exhibits.
    """

    def __init__(
        self,
        es_client: ElasticsearchClient,
        embeddings: CustomOllamaEmbeddings,
        chunk_configs: list[ChunkConfig] | None = None,
    ):
        self.es_client = es_client
        self.embeddings = embeddings
        self.chunk_configs = chunk_configs or [
            ChunkConfig(level=1, window_size=2000, overlap=200),
            ChunkConfig(level=2, window_size=500, overlap=50),
            ChunkConfig(level=3, window_size=100, overlap=10),
        ]

    async def index_source(
        self,
        source: ContentSource,
        max_concurrency: int = 10,
    ) -> int:
        """Index a content source to Elasticsearch.

        Args:
            source: The ContentSource to index.
            max_concurrency: Maximum concurrent ES indexing operations.

        Returns:
            Total number of chunks indexed.
        """
        total_chunks = 0
        prev_level_chunks: list = []

        for config in self.chunk_configs:
            chunker = TextChunker(config)
            current_level_chunks: list = []

            if not prev_level_chunks:
                chunks = chunker.chunk(
                    text=source.content,
                    document_id=source.source_id,
                    source=source.source_type,
                )
                current_level_chunks.extend(chunks)
            else:
                for parent in prev_level_chunks:
                    children = chunker.chunk(
                        text=parent.content,
                        document_id=source.source_id,
                        source=source.source_type,
                        parent_chunk_id=parent.id,
                    )
                    for child in children:
                        child.start_char += parent.start_char
                        child.end_char += parent.start_char
                    current_level_chunks.extend(children)

            if not current_level_chunks:
                continue

            chunk_texts = [c.content for c in current_level_chunks]
            embeddings_list = await self.embeddings.aembed_documents(chunk_texts)

            docs = []
            for chunk, embedding in zip(current_level_chunks, embeddings_list, strict=True):
                doc = {
                    "chunk_id": chunk.id,
                    "source_id": source.source_id,
                    "source_type": source.source_type,
                    "content": chunk.content,
                    "content_vector": embedding,
                    "chunk_level": chunk.level,
                    "parent_chunk_id": chunk.parent_chunk_id,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    "metadata": source.metadata.to_dict(),
                }
                docs.append(doc)
                total_chunks += 1

            semaphore = asyncio.Semaphore(max_concurrency)

            async def index_with_semaphore(
                doc: dict[str, Any],
                sem: asyncio.Semaphore = semaphore,
            ) -> None:
                async with sem:
                    await self.es_client.index_chunk(doc)

            await asyncio.gather(*[index_with_semaphore(doc) for doc in docs])

            prev_level_chunks = current_level_chunks

        logger.info(f"Indexed {total_chunks} chunks for source {source.source_id}")
        return total_chunks

    async def delete_source(
        self,
        source_id: str,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        """Delete all chunks for a source from Elasticsearch.

        Args:
            source_id: The ID of the source to delete.
            source_type: Optional source type filter.

        Returns:
            Result from Elasticsearch delete operation.
        """
        query: dict[str, Any]
        if source_type:
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"source_id": source_id}},
                            {"term": {"source_type": source_type}},
                        ]
                    }
                }
            }
        else:
            query = {"query": {"term": {"source_id": source_id}}}

        result = await self.es_client.delete_by_query(
            index=self.es_client.index_name,
            body=query,
        )
        logger.info(f"Deleted source {source_id} from index")
        return result
