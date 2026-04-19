from app.infra.providers.rerank.base import BaseRerankProvider, RerankResult


class MockRerankProvider(BaseRerankProvider):
    async def close(self) -> None:
        pass

    async def rerank(self, query: str, documents: list[str], top_n: int = 5) -> list[RerankResult]:
        if not documents:
            return []

        results = []
        query_lower = query.lower()

        for idx, doc in enumerate(documents):
            doc_lower = doc.lower()
            score = sum(1 for word in query_lower.split() if word in doc_lower) / max(len(query_lower.split()), 1)

            results.append(
                RerankResult(
                    index=idx,
                    relevance_score=score,
                    document=doc,
                )
            )

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_n]
