import pytest
from app.application.document_filter import DynamicDocumentFilter, FilterConfig
from langchain_core.documents import Document


class TestFilterConfig:
    def test_default_config(self):
        config = FilterConfig()
        assert config.absolute_threshold == 0.25
        assert config.relative_gap == 0.25
        assert config.min_docs == 1
        assert config.max_docs == 8

    def test_config_validation(self):
        with pytest.raises(ValueError, match="min_docs must be >= 1"):
            FilterConfig(min_docs=0)
        with pytest.raises(ValueError, match="max_docs must be >= min_docs"):
            FilterConfig(min_docs=5, max_docs=3)
        with pytest.raises(ValueError, match="absolute_threshold must be between 0 and 1"):
            FilterConfig(absolute_threshold=1.5)
        with pytest.raises(ValueError, match="relative_gap must be between 0 and 1"):
            FilterConfig(relative_gap=-0.1)


class TestDynamicDocumentFilter:
    def _make_docs(self, scores: list[float]) -> list[Document]:
        return [
            Document(page_content=f"doc{i}", metadata={"rerank_score": s})
            for i, s in enumerate(scores)
        ]

    def test_specific_exhibit_query(self):
        """连通灶场景: [0.41, 0.001, 0.00006] -> 应只保留1个"""
        docs = self._make_docs([0.41, 0.001, 0.00006])
        filter_obj = DynamicDocumentFilter()
        result = filter_obj.filter(docs)
        assert len(result) == 1
        assert result[0].metadata["rerank_score"] == pytest.approx(0.41)

    def test_broad_topic_query(self):
        """半坡陶器场景: [0.97, 0.97, 0.88] -> 应保留3个"""
        docs = self._make_docs([0.97, 0.97, 0.88])
        filter_obj = DynamicDocumentFilter()
        result = filter_obj.filter(docs)
        assert len(result) == 3

    def test_medium_scores_with_tail(self):
        """[0.8, 0.75, 0.72, 0.3, 0.1] -> 应保留前3个"""
        docs = self._make_docs([0.8, 0.75, 0.72, 0.3, 0.1])
        filter_obj = DynamicDocumentFilter()
        result = filter_obj.filter(docs)
        assert len(result) == 3

    def test_all_high_scores(self):
        """[0.95, 0.94, 0.93, 0.92, 0.91] -> 在max范围内全部保留"""
        docs = self._make_docs([0.95, 0.94, 0.93, 0.92, 0.91])
        filter_obj = DynamicDocumentFilter(FilterConfig(max_docs=5))
        result = filter_obj.filter(docs)
        assert len(result) == 5

    def test_all_low_scores(self):
        """[0.1, 0.05, 0.02] -> 绝对阈值过滤后保留min_docs个"""
        docs = self._make_docs([0.1, 0.05, 0.02])
        filter_obj = DynamicDocumentFilter()
        result = filter_obj.filter(docs)
        assert len(result) == 1

    def test_empty_docs(self):
        result = DynamicDocumentFilter().filter([])
        assert result == []

    def test_single_doc(self):
        docs = self._make_docs([0.5])
        result = DynamicDocumentFilter().filter(docs)
        assert len(result) == 1

    def test_no_rerank_scores_fallback(self):
        """没有 rerank_score 时应使用 rrf_score"""
        docs = [
            Document(page_content="a", metadata={"rrf_score": 0.8}),
            Document(page_content="b", metadata={"rrf_score": 0.3}),
        ]
        result = DynamicDocumentFilter().filter(docs)
        assert len(result) == 1
        assert result[0].metadata["rrf_score"] == pytest.approx(0.8)

    def test_mixed_scores_priority(self):
        """同时有 rerank_score 和 rrf_score 时优先 rerank_score"""
        docs = [
            Document(page_content="a", metadata={"rerank_score": 0.9, "rrf_score": 0.1}),
            Document(page_content="b", metadata={"rerank_score": 0.2, "rrf_score": 0.8}),
        ]
        result = DynamicDocumentFilter().filter(docs)
        assert len(result) == 1
        assert result[0].page_content == "a"
