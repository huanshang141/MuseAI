from typing import Any


def rrf_fusion(
    dense_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
    k: int = 60,
    deduplicate_by: str | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) 算法

    Args:
        dense_results: Dense 向量检索结果
        bm25_results: BM25 关键词检索结果
        k: RRF 参数，默认 60
        deduplicate_by: 按指定字段去重，保留分数最高的。None 表示不去重。
            当指定字段的值为 None 时，回退到 chunk_id 作为去重键（即视为唯一文档）。
        top_k: 返回的最大结果数。None 表示返回全部。

    Returns:
        融合后的结果列表，按 RRF 分数降序排列

    Raises:
        ValueError: k <= 0 or missing chunk_id in documents
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")

    if top_k is not None and top_k <= 0:
        raise ValueError(f"top_k must be positive, got {top_k}")

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
    seen_keys: set[str] = set()

    for chunk_id in sorted_chunk_ids:
        doc = doc_map[chunk_id].copy()
        doc["rrf_score"] = rrf_scores[chunk_id]

        if deduplicate_by:
            key = doc.get(deduplicate_by)
            if key is None:
                key = chunk_id
            if key in seen_keys:
                continue
            seen_keys.add(key)

        result.append(doc)

        if top_k is not None and len(result) >= top_k:
            break

    return result
