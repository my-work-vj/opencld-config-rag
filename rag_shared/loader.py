"""Load pipeline configuration from the database for runtime execution."""

from typing import Any

from sqlalchemy.orm import Session

from rag_shared.constants import INGESTION_STAGES, QUERY_STAGES
from rag_shared.models import RagPipeline
from rag_shared.repo import PipelineNotFoundError, PipelineRepo


def _sync_collection_name(stages: dict[str, Any]) -> dict[str, Any]:
    """Ensure knowledge_store reads the same collection as indexing writes."""
    indexing_cfg = stages.get("indexing", {}).get("config", {})
    collection = indexing_cfg.get("collection_name")
    if not collection:
        return stages

    stages = dict(stages)
    ks = dict(stages.get("knowledge_store", {"strategy": "qdrant_store", "config": {}}))
    ks_config = dict(ks.get("config", {}))
    ks_config.setdefault("collection_name", collection)
    ks["config"] = ks_config
    stages["knowledge_store"] = ks
    return stages


def _apply_model_aliases(record: RagPipeline, stages: dict[str, Any]) -> dict[str, Any]:
    """Inject top-level model aliases into stage configs when not explicitly set."""
    stages = dict(stages)

    if record.embedding_model:
        emb = dict(stages.get("embedding", {"strategy": "litellm_embedding", "config": {}}))
        emb_cfg = dict(emb.get("config", {}))
        emb_cfg.setdefault("model", record.embedding_model)
        emb["config"] = emb_cfg
        stages["embedding"] = emb

    if record.chat_model:
        resp = dict(stages.get("response", {"strategy": "contextual_response", "config": {}}))
        resp_cfg = dict(resp.get("config", {}))
        resp_cfg.setdefault("model", record.chat_model)
        if record.llm_params:
            for key in ("temperature", "max_tokens"):
                if key in record.llm_params and key not in resp_cfg:
                    resp_cfg[key] = record.llm_params[key]
        resp["config"] = resp_cfg
        stages["response"] = resp

        retr = dict(stages.get("retrieval", {"strategy": "vector_rag", "config": {}}))
        retr_cfg = dict(retr.get("config", {}))
        retr_cfg.setdefault("hyde_model", record.chat_model)
        retr["config"] = retr_cfg
        stages["retrieval"] = retr

    if record.reranker_model:
        rer = dict(stages.get("reranking", {"strategy": "litellm_reranking", "config": {}}))
        rer_cfg = dict(rer.get("config", {}))
        rer_cfg.setdefault("model", record.reranker_model)
        rer["config"] = rer_cfg
        stages["reranking"] = rer

    return stages


def _filter_stages(stages: dict[str, Any], allowed: tuple[str, ...]) -> dict[str, Any]:
    return {name: stages[name] for name in allowed if name in stages}


def record_to_runtime_config(
    record: RagPipeline,
    stage_filter: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Convert a DB record to the dict format expected by pipeline orchestrators."""
    stages = dict(record.stages or {})
    stages = _sync_collection_name(stages)
    stages = _apply_model_aliases(record, stages)

    if stage_filter:
        stages = _filter_stages(stages, stage_filter)

    return {
        "pipeline": {
            "id": record.id,
            "name": record.name,
            "description": record.description or "",
            "stages": stages,
            "embedding_model": record.embedding_model,
            "chat_model": record.chat_model,
            "reranker_model": record.reranker_model,
            "llm_params": record.llm_params or {},
            "status": record.status,
        }
    }


def load_ingestion_config(db: Session, pipeline_id: str) -> dict[str, Any]:
    record = PipelineRepo.get(db, pipeline_id)
    if record.status != "active":
        raise PipelineNotFoundError(f"Pipeline '{pipeline_id}' is not active")
    return record_to_runtime_config(record, INGESTION_STAGES)


def load_query_config(db: Session, pipeline_id: str) -> dict[str, Any]:
    record = PipelineRepo.get(db, pipeline_id)
    if record.status != "active":
        raise PipelineNotFoundError(f"Pipeline '{pipeline_id}' is not active")
    return record_to_runtime_config(record, QUERY_STAGES)
