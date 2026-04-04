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
    assert fused[0]["chunk_id"] in ["A", "B"]


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
