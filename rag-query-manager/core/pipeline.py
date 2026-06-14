"""QueryPipeline orchestrator — knowledge store selection through response."""

import time
import logging
from typing import Any

from .registry import StrategyRegistry
from .base_strategies import (
    KnowledgeStoreHandle,
    RetrievedChunk,
    PipelineContext,
    BaseKnowledgeStoreStrategy,
)

logger = logging.getLogger(__name__)


class QueryPipeline:
    """Orchestrates knowledge_store → retrieval → reranking → response."""

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

    def run_knowledge_store(self, **overrides) -> tuple[KnowledgeStoreHandle, BaseKnowledgeStoreStrategy]:
        cfg = self._merge_stage_config(
            self.stages_config.get("knowledge_store", {}), overrides
        )
        strategy, kwargs = self._load_strategy("knowledge_store", cfg)
        logger.info(f"[{self.name}] Knowledge store: {type(strategy).__name__}")
        handle = strategy.connect(**kwargs)
        return handle, strategy

    def run_retrieval(
        self,
        query: str,
        store: KnowledgeStoreHandle,
        knowledge_store_strategy: BaseKnowledgeStoreStrategy,
        **overrides,
    ) -> list[RetrievedChunk]:
        cfg = self._merge_stage_config(
            self.stages_config.get("retrieval", {}), overrides
        )
        strategy, kwargs = self._load_strategy("retrieval", cfg)
        logger.info(f"[{self.name}] Retrieval: {type(strategy).__name__}")
        return strategy.retrieve(
            query,
            store=store,
            knowledge_store_strategy=knowledge_store_strategy,
            **kwargs,
        )

    def run_reranking(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        **overrides,
    ) -> list[RetrievedChunk]:
        cfg = self._merge_stage_config(
            self.stages_config.get("reranking", {}), overrides
        )
        strategy, kwargs = self._load_strategy("reranking", cfg)
        logger.info(f"[{self.name}] Reranking: {type(strategy).__name__}")
        return strategy.rerank(query, chunks, **kwargs)

    def run_response(
        self,
        query: str,
        context_chunks: list[RetrievedChunk],
        **overrides,
    ) -> str:
        cfg = self._merge_stage_config(
            self.stages_config.get("response", {}), overrides
        )
        strategy, kwargs = self._load_strategy("response", cfg)
        logger.info(f"[{self.name}] Response: {type(strategy).__name__}")
        return strategy.generate(query, context_chunks, **kwargs)

    def run(
        self,
        query: str,
        knowledge_store_overrides: dict | None = None,
        retrieval_overrides: dict | None = None,
        reranking_overrides: dict | None = None,
        response_overrides: dict | None = None,
    ) -> PipelineContext:
        """Run the full query pipeline."""
        ctx = PipelineContext(pipeline_name=self.name, config=self.config, query=query)
        timings = {}

        t0 = time.time()
        store, ks_strategy = self.run_knowledge_store(**(knowledge_store_overrides or {}))
        ctx.knowledge_store = store
        ctx.state["knowledge_store_strategy"] = ks_strategy
        timings["knowledge_store"] = time.time() - t0
        logger.info(f"Connected to knowledge store: {store.collection_name}")

        t0 = time.time()
        ctx.retrieved_chunks = self.run_retrieval(
            query,
            store=store,
            knowledge_store_strategy=ks_strategy,
            **(retrieval_overrides or {}),
        )
        timings["retrieval"] = time.time() - t0
        logger.info(f"Retrieved {len(ctx.retrieved_chunks)} chunks")

        t0 = time.time()
        ctx.retrieved_chunks = self.run_reranking(
            query, ctx.retrieved_chunks, **(reranking_overrides or {})
        )
        timings["reranking"] = time.time() - t0

        t0 = time.time()
        ctx.response = self.run_response(
            query, ctx.retrieved_chunks, **(response_overrides or {})
        )
        timings["response"] = time.time() - t0

        ctx.state["timings"] = timings
        return ctx
