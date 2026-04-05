import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.chunking import ChunkConfig, TextChunker
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain.embeddings import CustomOllamaEmbeddings
from app.infra.postgres.models import IngestionJob

logger = logging.getLogger(__name__)


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
    ) -> int:
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
                await self.es_client.index_chunk(doc)
                total_chunks += 1

        return total_chunks

    async def process_document(
        self,
        session: AsyncSession,
        document_id: str,
        content: str,
        source: str | None = None,
    ) -> IngestionJob:
        job = await self._get_job(session, document_id)
        job.status = "processing"
        await session.flush()

        try:
            chunk_count = await self.ingest(document_id, content, source)
            job.status = "completed"
            job.chunk_count = chunk_count
            await session.flush()

            logger.info(f"Document {document_id} ingested: {chunk_count} chunks")
            return job

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            await session.flush()
            logger.error(f"Document {document_id} ingestion failed: {e}")
            raise

    async def _get_job(self, session: AsyncSession, document_id: str) -> IngestionJob:
        stmt = select(IngestionJob).where(IngestionJob.document_id == document_id)
        result = await session.execute(stmt)
        return result.scalar_one()
