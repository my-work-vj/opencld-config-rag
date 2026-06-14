"""Response generation strategies — contextual LLM response."""

import os
import logging
from typing import Optional

from dotenv import load_dotenv

from core.base_strategies import BaseResponseStrategy, RetrievedChunk
from core.registry import StrategyRegistry
from strategies.embedding import LiteLLMClient

load_dotenv()
logger = logging.getLogger(__name__)


@StrategyRegistry.register("response", "contextual_response")
class ContextualResponse(BaseResponseStrategy):
    """Generate a response using LiteLLM with retrieved context.

    Builds a prompt from the retrieved chunks and query, then calls
    the LLM via the LiteLLM proxy.
    """

    def __init__(self, **kwargs):
        self.client = LiteLLMClient.get_client().client
        self.model = kwargs.get("model", os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"))

    def _build_context(self, chunks: list[RetrievedChunk]) -> str:
        """Build a formatted context string from retrieved chunks."""
        sections = []
        for i, r in enumerate(chunks):
            source = r.chunk.filename or r.chunk.metadata.get("filename", f"chunk_{r.chunk.chunk_index}")
            sections.append(
                f"[Source: {source} | Score: {r.score:.4f} | Method: {r.retrieval_method}]\n"
                f"{r.chunk.content}\n"
            )
        return "\n---\n".join(sections)

    def _get_system_prompt(self, **kwargs) -> str:
        return kwargs.get(
            "system_prompt",
            (
                "You are a helpful RAG assistant. Answer the user's question based ONLY on "
                "the provided context. If the context doesn't contain enough information to "
                "answer the question, say so clearly. Cite your sources using [source: filename] notation."
            ),
        )

    def generate(self, query: str, context_chunks: list[RetrievedChunk], **kwargs) -> str:
        model = kwargs.get("model", self.model)
        temperature = kwargs.get("temperature", 0.3)
        max_tokens = kwargs.get("max_tokens", 2048)
        system_prompt = self._get_system_prompt(**kwargs)

        context = self._build_context(context_chunks)

        user_prompt = (
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            f"Answer based on the provided context:"
        )

        try:
            resp = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return f"Error generating response: {e}"
