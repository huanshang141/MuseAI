import json
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class KnowledgeRetrievalInput(BaseModel):
    query: str = Field(..., description="The query to search for")
    exhibit_id: str | None = Field(
        None, description="Optional specific exhibit ID to focus on"
    )


class KnowledgeRetrievalTool(BaseTool):
    name: str = "knowledge_retrieval"
    description: str = (
        "Retrieve knowledge about exhibits using the RAG system. "
        "Input should include a query string and optionally an exhibit_id "
        "to focus the search on a specific exhibit."
    )

    rag_agent: Any = Field(..., description="RAG Agent instance for retrieval")

    async def _arun(self, query: str) -> str:
        try:
            data = json.loads(query)
            input_data = KnowledgeRetrievalInput(**data)
        except (json.JSONDecodeError, Exception):
            input_data = KnowledgeRetrievalInput(query=query)

        try:
            search_query = input_data.query
            if input_data.exhibit_id:
                search_query = f"{input_data.query} (exhibit: {input_data.exhibit_id})"

            result = await self.rag_agent.run(search_query)

            sources = []
            docs = result.get("reranked_documents") or result.get("documents", [])
            for doc in docs:
                sources.append(
                    {
                        "content": doc.page_content[:200] + "..."
                        if len(doc.page_content) > 200
                        else doc.page_content,
                        "metadata": doc.metadata,
                    }
                )

            response = {
                "answer": result.get("answer", "No answer found."),
                "sources": sources[:3],
                "retrieval_score": result.get("retrieval_score", 0.0),
            }
            return json.dumps(response, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)})

    def _run(self, query: str) -> str:
        raise NotImplementedError("This tool only supports async execution")
