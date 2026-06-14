"""Reranking strategies — LiteLLM cross-encoder and pass-through."""

import os
import logging
from typing import Optional

import requests
from dotenv import load_dotenv

from core.base_strategies import BaseRerankingStrategy, RetrievedChunk
from core.registry import StrategyRegistry

load_dotenv()
logger = logging.getLogger(__name__)


@StrategyRegistry.register("reranking", "pass_through")
class PassThroughReranking(BaseRerankingStrategy):
    """No-op reranker — passes chunks through as-is, truncates to top_k."""

    def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        return chunks[:top_k]


@StrategyRegistry.register("reranking", "litellm_reranking")
class LiteLLMReranking(BaseRerankingStrategy):
    """Rerank using a cross-encoder reranker via LiteLLM's /v1/rerank endpoint.

    Uses the dedicated rerank endpoint (POST /v1/rerank) with model, query,
    and documents parameters. This is distinct from the embeddings API.
    """

    def __init__(self, **kwargs):
        self.base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1").rstrip("/v1")
        self.api_key = os.getenv("LITELLM_API_KEY", "sk-vj")
        self.model = kwargs.get("model", os.getenv("RERANKING_MODEL", "rerank-english-v3.0"))

    def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        if not chunks:
            return []

        model = kwargs.get("model", self.model)

        try:
            documents = [r.chunk.content[:2000] for r in chunks]

            resp = requests.post(
                f"{self.base_url}/v1/rerank",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "query": query,
                    "documents": documents,
                    "top_k": len(documents),
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            # Map relevance scores back to chunks
            scored = []
            for result in data.get("results", []):
                idx = result["index"]
                score = result.get("relevance_score", 0.0)
                new_r = RetrievedChunk(
                    chunk=chunks[idx].chunk,
                    score=score,
                    retrieval_method=f"{chunks[idx].retrieval_method}+rerank",
                )
                scored.append(new_r)

            # Results from /v1/rerank come sorted by score descending
            # but we sort again for safety
            scored.sort(key=lambda x: x.score, reverse=True)

        except Exception as e:
            logger.warning(f"Reranker API call failed: {e}. Falling back to original scores.")
            scored = list(chunks)
            scored.sort(key=lambda x: x.score, reverse=True)

        logger.info(f"Reranked {len(scored)} chunks → top {top_k} (model={model})")
        return scored[:top_k]
