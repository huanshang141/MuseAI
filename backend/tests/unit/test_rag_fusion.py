import pytest
from app.domain.services.retrieval import rrf_fusion


def test_rrf_fusion_basic():
    """基本融合测试"""
    dense_results = [
        {"chunk_id": "A", "content": "doc A"},
        {"chunk_id": "B", "content": "doc B"},
        {"chunk_id": "C", "content": "doc C"},
    ]
    bm25_results = [
        {"chunk_id": "B", "content": "doc B"},
        {"chunk_id": "D", "content": "doc D"},
        {"chunk_id": "A", "content": "doc A"},
    ]

    fused = rrf_fusion(dense_results, bm25_results, k=60)

    assert len(fused) == 4
    assert fused[0]["chunk_id"] == "B"
    assert fused[1]["chunk_id"] == "A"
    assert fused[2]["chunk_id"] == "D"
    assert fused[3]["chunk_id"] == "C"

    assert fused[0]["rrf_score"] == pytest.approx(1 / 62 + 1 / 61, rel=1e-4)
    assert fused[1]["rrf_score"] == pytest.approx(1 / 61 + 1 / 63, rel=1e-4)
    assert fused[2]["rrf_score"] == pytest.approx(1 / 62, rel=1e-4)
    assert fused[3]["rrf_score"] == pytest.approx(1 / 63, rel=1e-4)


def test_rrf_fusion_empty_lists():
    """空列表测试"""
    assert rrf_fusion([], []) == []
    assert rrf_fusion([{"chunk_id": "A"}], []) == [{"chunk_id": "A", "rrf_score": pytest.approx(1 / 61)}]


def test_rrf_fusion_custom_k():
    """自定义 k 参数测试"""
    dense_results = [{"chunk_id": "A"}]
    bm25_results = [{"chunk_id": "A"}]

    fused_k60 = rrf_fusion(dense_results, bm25_results, k=60)
    fused_k1 = rrf_fusion(dense_results, bm25_results, k=1)

    assert fused_k1[0]["rrf_score"] > fused_k60[0]["rrf_score"]


def test_rrf_fusion_preserves_metadata():
    """保留元数据测试"""
    dense_results = [
        {"chunk_id": "A", "content": "doc A", "title": "Title A"},
    ]
    bm25_results = [
        {"chunk_id": "A", "content": "doc A", "title": "Title A"},
    ]

    fused = rrf_fusion(dense_results, bm25_results)

    assert fused[0]["chunk_id"] == "A"
    assert fused[0]["content"] == "doc A"
    assert fused[0]["title"] == "Title A"
    assert "rrf_score" in fused[0]


def test_rrf_fusion_invalid_k():
    """k 参数验证测试"""
    with pytest.raises(ValueError, match="k must be positive"):
        rrf_fusion([{"chunk_id": "A"}], [], k=0)

    with pytest.raises(ValueError, match="k must be positive"):
        rrf_fusion([{"chunk_id": "A"}], [], k=-1)


def test_rrf_fusion_missing_chunk_id():
    """chunk_id 缺失验证测试"""
    with pytest.raises(ValueError, match="missing 'chunk_id' field"):
        rrf_fusion([{"content": "no id"}], [])

    with pytest.raises(ValueError, match="missing 'chunk_id' field"):
        rrf_fusion([], [{"content": "no id"}])


def test_rrf_fusion_deduplicates_by_source_id():
    dense = [
        {"chunk_id": "c1", "source_id": "doc-a", "content": "A1"},
        {"chunk_id": "c2", "source_id": "doc-a", "content": "A2"},
        {"chunk_id": "c3", "source_id": "doc-b", "content": "B1"},
    ]
    bm25 = [
        {"chunk_id": "c1", "source_id": "doc-a", "content": "A1"},
        {"chunk_id": "c3", "source_id": "doc-b", "content": "B1"},
        {"chunk_id": "c4", "source_id": "doc-c", "content": "C1"},
    ]
    result = rrf_fusion(dense, bm25, k=60, deduplicate_by="source_id", top_k=3)
    source_ids = [r["source_id"] for r in result]
    assert len(source_ids) == len(set(source_ids)), "Results should be deduplicated by source_id"
    assert "doc-a" in source_ids
    assert "doc-b" in source_ids
    assert "doc-c" in source_ids


def test_rrf_fusion_deduplicate_preserves_highest_score():
    dense = [
        {"chunk_id": "c1", "source_id": "doc-a", "content": "A1"},
        {"chunk_id": "c2", "source_id": "doc-a", "content": "A2"},
    ]
    bm25 = [
        {"chunk_id": "c1", "source_id": "doc-a", "content": "A1"},
    ]
    result = rrf_fusion(dense, bm25, k=60, deduplicate_by="source_id")
    assert len(result) == 1
    assert result[0]["chunk_id"] == "c1"


def test_rrf_fusion_deduplicate_fallback_to_chunk_id():
    dense = [
        {"chunk_id": "c1", "content": "A1"},
        {"chunk_id": "c2", "content": "A2"},
    ]
    bm25 = []
    result = rrf_fusion(dense, bm25, k=60, deduplicate_by="source_id")
    assert len(result) == 2


def test_rrf_fusion_top_k_limits_results():
    dense = [
        {"chunk_id": "c1", "source_id": "doc-a", "content": "A1"},
        {"chunk_id": "c2", "source_id": "doc-b", "content": "B1"},
        {"chunk_id": "c3", "source_id": "doc-c", "content": "C1"},
        {"chunk_id": "c4", "source_id": "doc-d", "content": "D1"},
    ]
    bm25 = []
    result = rrf_fusion(dense, bm25, k=60, top_k=2)
    assert len(result) == 2


def test_rrf_fusion_no_dedup_when_none():
    dense = [
        {"chunk_id": "c1", "source_id": "doc-a", "content": "A1"},
        {"chunk_id": "c2", "source_id": "doc-a", "content": "A2"},
    ]
    bm25 = []
    result = rrf_fusion(dense, bm25, k=60, deduplicate_by=None)
    assert len(result) == 2


def test_rrf_fusion_top_k_zero_raises():
    with pytest.raises(ValueError, match="top_k must be positive"):
        rrf_fusion([{"chunk_id": "c1"}], [], k=60, top_k=0)


def test_rrf_fusion_top_k_negative_raises():
    with pytest.raises(ValueError, match="top_k must be positive"):
        rrf_fusion([{"chunk_id": "c1"}], [], k=60, top_k=-1)


def test_rrf_fusion_top_k_greater_than_results():
    dense = [
        {"chunk_id": "c1", "content": "A1"},
        {"chunk_id": "c2", "content": "A2"},
    ]
    bm25 = []
    result = rrf_fusion(dense, bm25, k=60, top_k=10)
    assert len(result) == 2
