from typing import Any


def rrf_fusion(
    dense_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) 算法

    Args:
        dense_results: Dense 向量检索结果
        bm25_results: BM25 关键词检索结果
        k: RRF 参数，默认 60

    Returns:
        融合后的结果列表，按 RRF 分数降序排列

    Raises:
        ValueError: k <= 0 or missing chunk_id in documents
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")

    doc_map: dict[str, dict[str, Any]] = {}
    dense_ranks: dict[str, int] = {}
    bm25_ranks: dict[str, int] = {}

    for rank, doc in enumerate(dense_results, start=1):
        if "chunk_id" not in doc:
            raise ValueError(f"Document at rank {rank} in dense_results missing 'chunk_id' field")
        chunk_id = doc["chunk_id"]
        dense_ranks[chunk_id] = rank
        doc_map[chunk_id] = doc

    for rank, doc in enumerate(bm25_results, start=1):
        if "chunk_id" not in doc:
            raise ValueError(f"Document at rank {rank} in bm25_results missing 'chunk_id' field")
        chunk_id = doc["chunk_id"]
        bm25_ranks[chunk_id] = rank
        if chunk_id not in doc_map:
            doc_map[chunk_id] = doc

    rrf_scores: dict[str, float] = {}
    for chunk_id in doc_map:
        score = 0.0
        if chunk_id in dense_ranks:
            score += 1.0 / (k + dense_ranks[chunk_id])
        if chunk_id in bm25_ranks:
            score += 1.0 / (k + bm25_ranks[chunk_id])
        rrf_scores[chunk_id] = score

    sorted_chunk_ids = sorted(
        rrf_scores.keys(),
        key=lambda x: rrf_scores[x],
        reverse=True,
    )

    result = []
    for chunk_id in sorted_chunk_ids:
        doc = doc_map[chunk_id].copy()
        doc["rrf_score"] = rrf_scores[chunk_id]
        result.append(doc)

    return result
