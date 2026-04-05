import pytest
from app.application.retrieval import rrf_fusion


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
