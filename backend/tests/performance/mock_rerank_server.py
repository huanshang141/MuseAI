"""Mock Rerank server for performance testing.

Simulates a rerank API (SiliconFlow/Jina-compatible) with configurable delays.
"""
import asyncio
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from pydantic import BaseModel

from backend.tests.performance.config import get_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock Rerank Server")

# Global config (can be overridden)
config = get_config()


class RerankRequest(BaseModel):
    """Rerank request model."""

    model: str
    query: str
    documents: list[str]
    top_n: int = 5


class RerankResult(BaseModel):
    """Single rerank result."""

    index: int
    relevance_score: float
    document: str


class RerankResponse(BaseModel):
    """Rerank response model."""

    results: list[RerankResult]
    model: str


def generate_mock_scores(num_documents: int, top_n: int) -> list[dict[str, Any]]:
    """Generate mock rerank scores.

    Creates realistic-looking scores that decrease with index,
    simulating actual rerank behavior where more relevant documents
    appear earlier.
    """
    # Generate scores that roughly follow a descending pattern
    # but with some randomness to simulate real rerank behavior
    results = []

    # Shuffle indices to simulate reranking
    indices = list(range(num_documents))
    random.shuffle(indices)

    for rank, original_index in enumerate(indices):
        # Score decreases with rank, with some noise
        # Top results get high scores (0.8-1.0)
        # Lower results get progressively lower scores
        base_score = max(0.1, 1.0 - (rank / num_documents) * 0.8)
        noise = random.uniform(-0.05, 0.05)
        score = max(0.0, min(1.0, base_score + noise))

        results.append(
            {
                "index": original_index,
                "relevance_score": round(score, 4),
            }
        )

    # Sort by score descending and take top_n
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return results[:top_n]


@app.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest) -> RerankResponse:
    """Handle rerank requests (SiliconFlow/Jina-compatible)."""
    start_time = time.time()

    # Simulate processing delay based on number of documents
    # Rerank typically takes 100-500ms depending on document count
    base_delay_ms = config.mock_rerank_min_delay_ms
    per_doc_delay_ms = 5  # Additional delay per document
    delay_seconds = (base_delay_ms + len(request.documents) * per_doc_delay_ms) / 1000

    # Add some randomness
    delay_seconds += random.uniform(0, config.mock_rerank_max_delay_ms / 1000)
    await asyncio.sleep(delay_seconds)

    # Generate mock results
    top_n = min(request.top_n, len(request.documents))
    mock_results = generate_mock_scores(len(request.documents), top_n)

    # Add document text to results
    results = []
    for item in mock_results:
        results.append(
            RerankResult(
                index=item["index"],
                relevance_score=item["relevance_score"],
                document=request.documents[item["index"]][:200],  # Truncate for response
            )
        )

    duration_ms = int((time.time() - start_time) * 1000)
    logger.debug(f"Mock rerank completed in {duration_ms}ms for {len(request.documents)} documents")

    return RerankResponse(
        results=results,
        model=request.model,
    )


@app.post("/v1/rerank", response_model=RerankResponse)
async def rerank_v1(request: RerankRequest) -> RerankResponse:
    """Handle rerank requests with /v1/ prefix (alternative endpoint)."""
    return await rerank(request)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "mock-rerank"}


def run_server(port: int | None = None) -> None:
    """Run the mock rerank server."""
    import uvicorn

    port = port or config.mock_rerank_port
    uvicorn.run(app, host=config.mock_rerank_host, port=port)


if __name__ == "__main__":
    run_server()
