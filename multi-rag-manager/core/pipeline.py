"""RAGPipeline orchestrator — ties all stages together."""

import time
import logging
from typing import Any

from .registry import StrategyRegistry
from .base_strategies import (
    Document, Chunk, EmbeddingVector, RetrievedChunk, PipelineContext,
    BaseIngestionStrategy, BaseChunkingStrategy, BaseEmbeddingStrategy,
    BaseIndexingStrategy, BaseRetrievalStrategy, BaseRerankingStrategy,
    BaseResponseStrategy,
)

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Orchestrates the full RAG pipeline from ingestion to response."""

    def __init__(self, pipeline_config: dict[str, Any]):
        self.name = pipeline_config.get("pipeline", {}).get("name", "unnamed")
        self.config = pipeline_config.get("pipeline", {})
        self.stages_config = self.config.get("stages", {})

    @staticmethod
    def _load_strategy(stage_name: str, strategy_config: dict) -> Any:
        """Load a strategy from the registry with its config."""
        strategy_name = strategy_config.get("strategy")
        strategy_kwargs = strategy_config.get("config", {})
        strategy = StrategyRegistry.get(stage_name, strategy_name)
        # If it's a class (not instance), instantiate it
        if isinstance(strategy, type):
            strategy = strategy()
        return strategy, strategy_kwargs

    def run_ingestion(self, source: Any, **overrides) -> list[Document]:
        """Stage 1: Ingest documents."""
        cfg = self.stages_config.get("ingestion", {})
        strategy, kwargs = self._load_strategy("ingestion", {**cfg, **overrides})
        logger.info(f"[{self.name}] Ingestion: {type(strategy).__name__}")
        return strategy.ingest(source, **kwargs)

    def run_chunking(self, documents: list[Document], **overrides) -> list[Chunk]:
        """Stage 2: Chunk documents."""
        cfg = self.stages_config.get("chunking", {})
        strategy, kwargs = self._load_strategy("chunking", {**cfg, **overrides})
        logger.info(f"[{self.name}] Chunking: {type(strategy).__name__}")
        return strategy.chunk(documents, **kwargs)

    def run_embedding(self, chunks: list[Chunk], **overrides) -> list[EmbeddingVector]:
        """Stage 3: Generate embeddings."""
        cfg = self.stages_config.get("embedding", {})
        strategy, kwargs = self._load_strategy("embedding", {**cfg, **overrides})
        logger.info(f"[{self.name}] Embedding: {type(strategy).__name__}")
        return strategy.embed(chunks, **kwargs)

    def run_indexing(self, embeddings: list[EmbeddingVector], **overrides) -> None:
        """Stage 4: Index embeddings."""
        cfg = self.stages_config.get("indexing", {})
        strategy, kwargs = self._load_strategy("indexing", {**cfg, **overrides})
        logger.info(f"[{self.name}] Indexing: {type(strategy).__name__}")
        strategy.index(embeddings, **kwargs)

    def run_retrieval(self, query: str, **overrides) -> list[RetrievedChunk]:
        """Stage 5: Retrieve relevant chunks."""
        cfg = self.stages_config.get("retrieval", {})
        strategy, kwargs = self._load_strategy("retrieval", {**cfg, **overrides})
        logger.info(f"[{self.name}] Retrieval: {type(strategy).__name__}")
        return strategy.retrieve(query, **kwargs)

    def run_reranking(self, query: str, chunks: list[RetrievedChunk], **overrides) -> list[RetrievedChunk]:
        """Stage 6: Re-rank retrieved chunks."""
        cfg = self.stages_config.get("reranking", {})
        strategy, kwargs = self._load_strategy("reranking", {**cfg, **overrides})
        logger.info(f"[{self.name}] Reranking: {type(strategy).__name__}")
        return strategy.rerank(query, chunks, **kwargs)

    def run_response(self, query: str, context_chunks: list[RetrievedChunk], **overrides) -> str:
        """Stage 7: Generate final response."""
        cfg = self.stages_config.get("response", {})
        strategy, kwargs = self._load_strategy("response", {**cfg, **overrides})
        logger.info(f"[{self.name}] Response: {type(strategy).__name__}")
        return strategy.generate(query, context_chunks, **kwargs)

    def run_ingestion_pipeline(
        self,
        source: Any,
        ingestion_overrides: dict | None = None,
        chunking_overrides: dict | None = None,
        embedding_overrides: dict | None = None,
        indexing_overrides: dict | None = None,
    ) -> PipelineContext:
        """Run ingestion stages only (ingest → chunk → embed → index)."""
        ctx = PipelineContext(pipeline_name=self.name, config=self.config)
        timings = {}

        # 1. Ingestion
        t0 = time.time()
        ctx.documents = self.run_ingestion(source, **(ingestion_overrides or {}))
        timings["ingestion"] = time.time() - t0
        logger.info(f"Ingested {len(ctx.documents)} documents")

        # 2. Chunking
        t0 = time.time()
        ctx.chunks = self.run_chunking(ctx.documents, **(chunking_overrides or {}))
        timings["chunking"] = time.time() - t0
        logger.info(f"Created {len(ctx.chunks)} chunks")

        # 3. Embedding
        t0 = time.time()
        ctx.embeddings = self.run_embedding(ctx.chunks, **(embedding_overrides or {}))
        timings["embedding"] = time.time() - t0
        logger.info(f"Generated {len(ctx.embeddings)} embeddings")

        # 4. Indexing
        t0 = time.time()
        self.run_indexing(ctx.embeddings, **(indexing_overrides or {}))
        timings["indexing"] = time.time() - t0
        logger.info("Indexing complete")

        ctx.state["timings"] = timings
        return ctx

    def run_full_pipeline(
        self,
        source: Any,
        query: str,
        ingestion_overrides: dict | None = None,
        chunking_overrides: dict | None = None,
        embedding_overrides: dict | None = None,
        indexing_overrides: dict | None = None,
        retrieval_overrides: dict | None = None,
        reranking_overrides: dict | None = None,
        response_overrides: dict | None = None,
    ) -> PipelineContext:
        """Run the full RAG pipeline end-to-end (ingestion + query)."""
        ctx = self.run_ingestion_pipeline(
            source=source,
            ingestion_overrides=ingestion_overrides,
            chunking_overrides=chunking_overrides,
            embedding_overrides=embedding_overrides,
            indexing_overrides=indexing_overrides,
        )

        # 5. Retrieval
        ctx.query = query
        t0 = time.time()
        ctx.retrieved_chunks = self.run_retrieval(query, **(retrieval_overrides or {}))
        timings = ctx.state.get("timings", {})
        timings["retrieval"] = time.time() - t0
        logger.info(f"Retrieved {len(ctx.retrieved_chunks)} chunks")

        # 6. Reranking
        t0 = time.time()
        ctx.retrieved_chunks = self.run_reranking(
            query, ctx.retrieved_chunks, **(reranking_overrides or {})
        )
        timings["reranking"] = time.time() - t0
        logger.info(f"After reranking: {len(ctx.retrieved_chunks)} chunks")

        # 7. Response
        t0 = time.time()
        ctx.response = self.run_response(query, ctx.retrieved_chunks, **(response_overrides or {}))
        timings["response"] = time.time() - t0
        logger.info("Response generated")

        ctx.state["timings"] = timings
        return ctx

    def run_query_only(
        self,
        query: str,
        retrieval_overrides: dict | None = None,
        reranking_overrides: dict | None = None,
        response_overrides: dict | None = None,
    ) -> PipelineContext:
        """Run only the query stages (retrieval → reranking → response).
        Assumes documents are already indexed."""
        ctx = PipelineContext(pipeline_name=self.name, config=self.config)
        timings = {}

        ctx.query = query

        # 5. Retrieval
        t0 = time.time()
        ctx.retrieved_chunks = self.run_retrieval(query, **(retrieval_overrides or {}))
        timings["retrieval"] = time.time() - t0
        logger.info(f"Retrieved {len(ctx.retrieved_chunks)} chunks")

        # 6. Reranking
        t0 = time.time()
        ctx.retrieved_chunks = self.run_reranking(
            query, ctx.retrieved_chunks, **(reranking_overrides or {})
        )
        timings["reranking"] = time.time() - t0

        # 7. Response
        t0 = time.time()
        ctx.response = self.run_response(query, ctx.retrieved_chunks, **(response_overrides or {}))
        timings["response"] = time.time() - t0

        ctx.state["timings"] = timings
        return ctx
