"""IngestionPipeline orchestrator — ingestion through knowledge store indexing."""

import time
import logging
from typing import Any

from .registry import StrategyRegistry
from .base_strategies import (
    Document,
    Chunk,
    EmbeddingVector,
    PipelineContext,
)

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates ingestion → chunking → embedding → indexing."""

    def __init__(self, pipeline_config: dict[str, Any]):
        self.name = pipeline_config.get("pipeline", {}).get("name", "unnamed")
        self.config = pipeline_config.get("pipeline", {})
        self.stages_config = self.config.get("stages", {})

    @staticmethod
    def _merge_stage_config(base: dict, overrides: dict) -> dict:
        merged = dict(base)
        if overrides.get("strategy"):
            merged["strategy"] = overrides["strategy"]
        merged_config = dict(base.get("config", {}))
        merged_config.update(overrides.get("config", {}))
        merged["config"] = merged_config
        return merged

    @staticmethod
    def _load_strategy(stage_name: str, strategy_config: dict) -> tuple[Any, dict]:
        strategy_name = strategy_config.get("strategy")
        strategy_kwargs = strategy_config.get("config", {})
        strategy = StrategyRegistry.get(stage_name, strategy_name)
        return strategy, strategy_kwargs

    def run_ingestion(self, source: Any, **overrides) -> list[Document]:
        cfg = self._merge_stage_config(
            self.stages_config.get("ingestion", {}), overrides
        )
        strategy, kwargs = self._load_strategy("ingestion", cfg)
        logger.info(f"[{self.name}] Ingestion: {type(strategy).__name__}")
        return strategy.ingest(source, **kwargs)

    def run_chunking(self, documents: list[Document], **overrides) -> list[Chunk]:
        cfg = self._merge_stage_config(
            self.stages_config.get("chunking", {}), overrides
        )
        strategy, kwargs = self._load_strategy("chunking", cfg)
        logger.info(f"[{self.name}] Chunking: {type(strategy).__name__}")
        return strategy.chunk(documents, **kwargs)

    def run_embedding(self, chunks: list[Chunk], **overrides) -> list[EmbeddingVector]:
        cfg = self._merge_stage_config(
            self.stages_config.get("embedding", {}), overrides
        )
        strategy, kwargs = self._load_strategy("embedding", cfg)
        logger.info(f"[{self.name}] Embedding: {type(strategy).__name__}")
        return strategy.embed(chunks, **kwargs)

    def run_indexing(self, embeddings: list[EmbeddingVector], **overrides) -> None:
        cfg = self._merge_stage_config(
            self.stages_config.get("indexing", {}), overrides
        )
        strategy, kwargs = self._load_strategy("indexing", cfg)
        logger.info(f"[{self.name}] Indexing: {type(strategy).__name__}")
        strategy.index(embeddings, **kwargs)

    def run(
        self,
        source: Any,
        ingestion_overrides: dict | None = None,
        chunking_overrides: dict | None = None,
        embedding_overrides: dict | None = None,
        indexing_overrides: dict | None = None,
    ) -> PipelineContext:
        """Run the full ingestion pipeline."""
        ctx = PipelineContext(pipeline_name=self.name, config=self.config)
        timings = {}

        t0 = time.time()
        ctx.documents = self.run_ingestion(source, **(ingestion_overrides or {}))
        timings["ingestion"] = time.time() - t0
        logger.info(f"Ingested {len(ctx.documents)} documents")

        t0 = time.time()
        ctx.chunks = self.run_chunking(ctx.documents, **(chunking_overrides or {}))
        timings["chunking"] = time.time() - t0
        logger.info(f"Created {len(ctx.chunks)} chunks")

        t0 = time.time()
        ctx.embeddings = self.run_embedding(ctx.chunks, **(embedding_overrides or {}))
        timings["embedding"] = time.time() - t0
        logger.info(f"Generated {len(ctx.embeddings)} embeddings")

        t0 = time.time()
        self.run_indexing(ctx.embeddings, **(indexing_overrides or {}))
        timings["indexing"] = time.time() - t0
        logger.info("Indexing complete")

        ctx.state["timings"] = timings
        ctx.state["collection_name"] = (
            self.stages_config.get("indexing", {}).get("config", {}).get("collection_name", "rag_documents")
        )
        return ctx
