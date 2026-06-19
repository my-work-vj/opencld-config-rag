"""Agent pipeline YAML seed and export helpers."""

import logging
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from rag_shared.models import Agent
from rag_shared.schemas import CreateAgentRequest
from rag_shared.yaml_export import export_agent_pipeline

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AGENT_PIPELINES_DIR = REPO_ROOT / "agent_pipelines"


def agent_to_yaml_doc(agent: Agent) -> dict[str, Any]:
    kb_names = list(agent.knowledge_base_names or [])
    if not kb_names and agent.knowledge_base_name:
        kb_names = [agent.knowledge_base_name]

    doc: dict[str, Any] = {
        "id": agent.name,
        "name": agent.name,
        "description": agent.description or "",
        "is_active": bool(agent.is_active),
    }

    if agent.prompt_template_id:
        prompt_block: dict[str, Any] = {"template_id": agent.prompt_template_id}
        if agent.prompt_version is not None:
            prompt_block["version"] = agent.prompt_version
        doc["prompt"] = prompt_block

    if kb_names:
        doc["knowledge_bases"] = kb_names

    query_stages = agent.query_stages or {}
    if not query_stages:
        query_stages = {
            "retrieval": {
                "strategy": agent.retrieval_strategy,
                "config": {**(agent.retrieval_config or {}), "top_k": agent.top_k},
            },
            "reranking": {
                "strategy": agent.reranking_strategy,
                "config": agent.reranking_config or {},
            },
            "response": {
                "strategy": agent.response_strategy or "contextual_response",
                "config": {
                    **(agent.response_config or {}),
                    "model": agent.llm_model,
                },
            },
        }
    doc["query_stages"] = query_stages
    return doc


def export_agent_record(agent: Agent) -> tuple[str | None, Any]:
    doc = agent_to_yaml_doc(agent)
    return export_agent_pipeline(doc)


def _parse_agent_yaml_file(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw.get("agent_pipeline", raw)


def yaml_doc_to_create_request(doc: dict[str, Any]) -> CreateAgentRequest:
    prompt = doc.get("prompt") or {}
    query_stages = doc.get("query_stages") or {}
    retrieval = query_stages.get("retrieval", {})
    reranking = query_stages.get("reranking", {})
    response = query_stages.get("response", {})

    retrieval_config = dict(retrieval.get("config") or {})
    top_k = retrieval_config.pop("top_k", 5)

    response_config = dict(response.get("config") or {})
    llm_model = response_config.pop("model", "llama-3.3-70b-versatile")

    return CreateAgentRequest(
        name=doc["id"],
        description=doc.get("description", ""),
        knowledge_base_names=doc.get("knowledge_bases") or [],
        prompt_template_id=prompt.get("template_id"),
        prompt_version=prompt.get("version"),
        llm_model=llm_model,
        retrieval_strategy=retrieval.get("strategy", "multi_collection"),
        top_k=top_k,
        reranking_strategy=reranking.get("strategy", "pass_through"),
        response_strategy=response.get("strategy", "contextual_response"),
        retrieval_config=retrieval_config,
        reranking_config=reranking.get("config") or {},
        response_config=response_config,
        query_stages=query_stages,
        is_active=doc.get("is_active", True),
    )


def seed_from_directory(
    db: Session,
    directory: Path | None = None,
    dry_run: bool = False,
) -> list[str]:
    from rag_shared.knowledge_repo import AgentRepo

    folder = directory or DEFAULT_AGENT_PIPELINES_DIR
    if not folder.exists():
        logger.warning(f"Agent pipelines directory not found: {folder}")
        return []

    seeded: list[str] = []
    for path in sorted(folder.glob("*.yaml")) + sorted(folder.glob("*.yml")):
        doc = _parse_agent_yaml_file(path)
        agent_id = doc.get("id") or path.stem
        if dry_run:
            logger.info(f"[dry-run] Would upsert agent pipeline '{agent_id}' from {path.name}")
            seeded.append(agent_id)
            continue
        req = yaml_doc_to_create_request(doc)
        try:
            existing = db.query(Agent).filter(Agent.name == req.name).first()
            if existing:
                from rag_shared.schemas import UpdateAgentRequest

                AgentRepo.update(
                    db,
                    req.name,
                    UpdateAgentRequest(
                        description=req.description,
                        knowledge_base_names=req.knowledge_base_names,
                        prompt_template_id=req.prompt_template_id,
                        prompt_version=req.prompt_version,
                        llm_model=req.llm_model,
                        retrieval_strategy=req.retrieval_strategy,
                        top_k=req.top_k,
                        reranking_strategy=req.reranking_strategy,
                        response_strategy=req.response_strategy,
                        retrieval_config=req.retrieval_config,
                        reranking_config=req.reranking_config,
                        response_config=req.response_config,
                        query_stages=req.query_stages,
                        is_active=req.is_active,
                    ),
                )
            else:
                AgentRepo.create(db, req)
            seeded.append(agent_id)
        except Exception as e:
            logger.error(f"Failed to seed agent from {path.name}: {e}")
            raise
    return seeded
