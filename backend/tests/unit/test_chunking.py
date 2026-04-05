from app.application.chunking import ChunkConfig, TextChunker


def test_chunk_text_l1():
    chunker = TextChunker(ChunkConfig(level=1, window_size=2000, overlap=200))
    text = "A" * 5000
    chunks = chunker.chunk(text)
    assert len(chunks) >= 2
    assert all(len(c.content) <= 2000 for c in chunks)


def test_chunk_text_l2():
    chunker = TextChunker(ChunkConfig(level=2, window_size=500, overlap=50))
    text = "Hello world. " * 100
    chunks = chunker.chunk(text)
    assert len(chunks) >= 2
    assert all(len(c.content) <= 500 for c in chunks)


def test_chunk_text_l3():
    chunker = TextChunker(ChunkConfig(level=3, window_size=100, overlap=20))
    text = "Short sentence. " * 20
    chunks = chunker.chunk(text)
    assert len(chunks) >= 2


def test_chunk_preserves_overlap():
    chunker = TextChunker(ChunkConfig(level=2, window_size=100, overlap=20))
    text = "A" * 50 + "B" * 50 + "C" * 50
    chunks = chunker.chunk(text)
    if len(chunks) > 1:
        overlap_found = False
        for i in range(len(chunks) - 1):
            end_of_first = chunks[i].content[-20:]
            start_of_second = chunks[i + 1].content[:20]
            if end_of_first == start_of_second:
                overlap_found = True
                break
        assert overlap_found or len(chunks) == 1


def test_chunk_metadata():
    chunker = TextChunker(ChunkConfig(level=2, window_size=100, overlap=20))
    text = "Test content for chunking."
    chunks = chunker.chunk(text, document_id="doc-123", source="test.pdf")
    assert chunks[0].document_id == "doc-123"
    assert chunks[0].source == "test.pdf"
    assert chunks[0].level == 2
