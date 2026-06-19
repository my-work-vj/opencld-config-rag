"""Run queries through named Agents."""

import logging
import time
from typing import Any

from fastapi import HTTPException

from core.base_strategies import KnowledgeStoreHandle
from core.registry import StrategyRegistry
from rag_shared.db import SessionLocal
from rag_shared.knowledge_repo import AgentNotFoundError, AgentRepo, KnowledgeBaseRepo
from rag_shared.prompt_repo import PromptTemplateRepo
from rag_shared.schemas import AgentQueryResponse, ChunkResult

logger = logging.getLogger(__name__)


def _chunks_to_results(chunks) -> list[ChunkResult]:
    results = []
    for r in chunks:
        source_collection = r.chunk.metadata.get("source_collection")
        results.append(
            ChunkResult(
                content=r.chunk.content[:500],
                score=r.score,
                retrieval_method=r.retrieval_method,
                filename=r.chunk.filename or r.chunk.metadata.get("filename"),
                chunk_index=r.chunk.chunk_index,
                source_collection=source_collection,
            )
        )
    return results


def _resolve_agent_prompt(db, agent) -> tuple[str, str]:
    if agent.prompt_template_id:
        return PromptTemplateRepo.resolve_prompt(
            db,
            agent.prompt_template_id,
            agent.prompt_version,
            agent.system_prompt or "",
        )
    return agent.system_prompt or "", ""


def _get_kb_names(agent) -> list[str]:
    names = list(agent.knowledge_base_names or [])
    if not names and agent.knowledge_base_name:
        names = [agent.knowledge_base_name]
    return names


def run_agent_query(agent_name: str, query: str, top_k_override: int | None = None) -> AgentQueryResponse:
    db = SessionLocal()
    try:
        try:
            agent = AgentRepo.get(db, agent_name)
        except AgentNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

        if not agent.is_active:
            raise HTTPException(status_code=422, detail=f"Agent '{agent_name}' is not active")

        kb_names = _get_kb_names(agent)
        if not kb_names and not agent.knowledge_source_name:
            raise HTTPException(
                status_code=422,
                detail="Agent has no knowledge_base_names or knowledge_source_name",
            )

        top_k = top_k_override or agent.top_k
        system_prompt, user_prompt_template = _resolve_agent_prompt(db, agent)
        timings: dict[str, float] = {}
        sources_searched: list[str] = []
        chunks: list[Any] = []
        response = ""

        t0_total = time.time()

        if kb_names:
            collections = KnowledgeBaseRepo.merge_collections(db, kb_names)
            sources_searched = [s.get("collection_name", "") for s in collections]
            knowledge_target = f"knowledge_bases:{','.join(kb_names)}"

            retrieval_strategy = agent.retrieval_strategy or "multi_collection"
            retrieval_config = dict(agent.retrieval_config or {})
            retrieval_config.setdefault("top_k", top_k)

            t0 = time.time()
            if retrieval_strategy == "multi_collection":
                retrieval = StrategyRegistry.get(
                    "retrieval",
                    "multi_collection",
                    collections=collections,
                )
                dummy_store = KnowledgeStoreHandle(store_type="multi", collection_name="multi")
                chunks = retrieval.retrieve(
                    query,
                    store=dummy_store,
                    knowledge_store_strategy=None,
                    top_k=top_k,
                    collections=collections,
                    **retrieval_config,
                )
            else:
                if len(collections) != 1:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Strategy '{retrieval_strategy}' requires exactly one collection",
                    )
                col = collections[0]
                retrieval = StrategyRegistry.get(
                    "retrieval",
                    retrieval_strategy,
                    **retrieval_config,
                )
                store = KnowledgeStoreHandle(
                    store_type="qdrant",
                    collection_name=col.get("collection_name", ""),
                )
                chunks = retrieval.retrieve(
                    query,
                    store=store,
                    knowledge_store_strategy=None,
                    top_k=top_k,
                    **retrieval_config,
                )
            timings["retrieval"] = time.time() - t0
            retrieval_method = retrieval_strategy

        else:
            from rag_shared.knowledge_repo import KnowledgeSourceRepo
            from rag_shared.collection_loader import load_collection_query_config
            from core.pipeline import QueryPipeline

            ks = KnowledgeSourceRepo.get(db, agent.knowledge_source_name)
            knowledge_target = f"knowledge_source:{ks.name}"
            sources_searched = [ks.collection_name]

            config = load_collection_query_config(db, ks.name)
            pipeline = QueryPipeline(config)
            t0 = time.time()
            ctx = pipeline.run(
                query=query,
                knowledge_store_overrides={
                    "config": {"collection_name": ks.collection_name, "validate": True},
                },
                retrieval_overrides={
                    "strategy": agent.retrieval_strategy,
                    "config": {**(agent.retrieval_config or {}), "top_k": top_k},
                },
                reranking_overrides={
                    "strategy": agent.reranking_strategy,
                    "config": {**(agent.reranking_config or {}), "top_k": top_k},
                },
                response_overrides={
                    "strategy": agent.response_strategy or "contextual_response",
                    "config": {
                        **(agent.response_config or {}),
                        "model": agent.llm_model,
                        "system_prompt": system_prompt,
                    },
                },
            )
            timings.update(ctx.state.get("timings", {}))
            chunks = ctx.retrieved_chunks
            response = ctx.response
            methods = set(r.retrieval_method for r in chunks)
            retrieval_method = "+".join(sorted(methods)) if methods else agent.retrieval_strategy

            total_time_ms = (time.time() - t0_total) * 1000
            return AgentQueryResponse(
                query=query,
                agent_name=agent.name,
                knowledge_target=knowledge_target,
                sources_searched=sources_searched,
                response=response,
                retrieval_method=retrieval_method,
                chunks=_chunks_to_results(chunks),
                timings=timings,
                total_time_ms=total_time_ms,
            )

        t0 = time.time()
        rerank_strategy = StrategyRegistry.get(
            "reranking",
            agent.reranking_strategy,
            **(agent.reranking_config or {}),
        )
        chunks = rerank_strategy.rerank(
            query,
            chunks,
            top_k=top_k,
            **(agent.reranking_config or {}),
        )
        timings["reranking"] = time.time() - t0

        t0 = time.time()
        response_strategy_name = agent.response_strategy or "contextual_response"
        response_strategy = StrategyRegistry.get(
            "response",
            response_strategy_name,
            **(agent.response_config or {}),
        )
        response_kwargs = {
            "model": agent.llm_model,
            "system_prompt": system_prompt,
            **(agent.response_config or {}),
        }
        if user_prompt_template:
            response_kwargs["user_prompt_template"] = user_prompt_template
        response = response_strategy.generate(query, chunks, **response_kwargs)
        timings["response"] = time.time() - t0
        retrieval_method = agent.retrieval_strategy or "multi_collection"

        total_time_ms = (time.time() - t0_total) * 1000

        return AgentQueryResponse(
            query=query,
            agent_name=agent.name,
            knowledge_target=knowledge_target,
            sources_searched=sources_searched,
            response=response,
            retrieval_method=retrieval_method,
            chunks=_chunks_to_results(chunks),
            timings=timings,
            total_time_ms=total_time_ms,
        )
    finally:
        db.close()
