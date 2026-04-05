import uuid
from dataclasses import dataclass


@dataclass
class ChunkConfig:
    level: int
    window_size: int
    overlap: int


@dataclass
class Chunk:
    id: str
    document_id: str
    level: int
    content: str
    source: str | None = None
    parent_chunk_id: str | None = None
    start_char: int = 0
    end_char: int = 0


class TextChunker:
    def __init__(self, config: ChunkConfig):
        self.config = config

    def chunk(
        self, text: str, document_id: str = "", source: str | None = None, parent_chunk_id: str | None = None
    ) -> list[Chunk]:
        if not text:
            return []

        chunks = []
        text_length = len(text)
        start = 0
        chunk_index = 0

        while start < text_length:
            end = min(start + self.config.window_size, text_length)
            chunk_content = text[start:end]

            chunk = Chunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                level=self.config.level,
                content=chunk_content,
                source=source,
                parent_chunk_id=parent_chunk_id,
                start_char=start,
                end_char=end,
            )
            chunks.append(chunk)

            next_start = end - self.config.overlap
            if next_start <= start:
                next_start = end
            start = next_start
            chunk_index += 1

        return chunks
