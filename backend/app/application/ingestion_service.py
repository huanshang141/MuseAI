import asyncio

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.chunking import ChunkConfig, TextChunker
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain.embeddings import CustomOllamaEmbeddings
from app.infra.postgres.models import Document, IngestionJob


class IngestionService:
    """文档摄取服务"""

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

    async def ingest(
        self,
        document_id: str,
        content: str,
        source: str | None = None,
        max_concurrency: int = 10,
    ) -> int:
        """Ingest document content into Elasticsearch with parallel indexing.

        Args:
            document_id: Document identifier
            content: Document text content
            source: Source filename
            max_concurrency: Maximum concurrent ES indexing operations

        Returns:
            Total number of chunks indexed
        """
        total_chunks = 0

        for config in self.chunk_configs:
            chunker = TextChunker(config)
            chunks = chunker.chunk(
                text=content,
                document_id=document_id,
                source=source,
            )

            if not chunks:
                continue

            chunk_texts = [c.content for c in chunks]
            embeddings_list = await self.embeddings.aembed_documents(chunk_texts)

            # Prepare all documents with embeddings
            docs = []
            for chunk, embedding in zip(chunks, embeddings_list):
                doc = {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "chunk_level": chunk.level,
                    "content": chunk.content,
                    "content_vector": embedding,
                    "source": chunk.source,
                    "parent_chunk_id": chunk.parent_chunk_id,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                }
                docs.append(doc)
                total_chunks += 1

            # Index to Elasticsearch concurrently with semaphore
            semaphore = asyncio.Semaphore(max_concurrency)

            async def index_with_semaphore(doc: dict) -> None:
                async with semaphore:
                    await self.es_client.index_chunk(doc)

            await asyncio.gather(*[index_with_semaphore(doc) for doc in docs])

        return total_chunks

    async def process_document(
        self,
        session: AsyncSession,
        document_id: str,
        content: str,
        source: str | None = None,
    ) -> IngestionJob:
        job = await self._get_job(session, document_id)
        document = await self._get_document(session, document_id)
        job.status = "processing"
        document.status = "processing"
        await session.flush()

        try:
            chunk_count = await self.ingest(document_id, content, source)
            job.status = "completed"
            job.chunk_count = chunk_count
            document.status = "completed"
            await session.flush()

            logger.info(f"Document {document_id} ingested: {chunk_count} chunks")
            return job

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            document.status = "failed"
            document.error = str(e)
            await session.flush()
            logger.error(f"Document {document_id} ingestion failed: {e}")
            raise

    async def _get_job(self, session: AsyncSession, document_id: str) -> IngestionJob:
        stmt = select(IngestionJob).where(IngestionJob.document_id == document_id)
        result = await session.execute(stmt)
        return result.scalar_one()

    async def _get_document(self, session: AsyncSession, document_id: str) -> Document:
        stmt = select(Document).where(Document.id == document_id)
        result = await session.execute(stmt)
        return result.scalar_one()
