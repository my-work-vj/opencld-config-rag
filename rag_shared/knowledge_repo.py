"""Knowledge Source, Knowledge Base, and Agent repositories."""

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from rag_shared.models import Agent, KnowledgeBase, KnowledgeSource
from rag_shared.prompt_repo import PromptTemplateNotFoundError, PromptTemplateRepo
from rag_shared.schemas import (
    CreateAgentRequest,
    CreateKnowledgeBaseRequest,
    CreateKnowledgeSourceRequest,
    UpdateAgentRequest,
    UpdateKnowledgeBaseRequest,
)
from rag_shared.slug import slugify_name

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer based on the provided context."
)


class KnowledgeSourceNotFoundError(Exception):
    pass


class KnowledgeBaseNotFoundError(Exception):
    pass


class AgentNotFoundError(Exception):
    pass


def _ks_to_info(record: KnowledgeSource) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "description": record.description or "",
        "collection_name": record.collection_name,
        "pipeline_id": record.pipeline_id,
        "embedding_model": record.embedding_model or "",
        "vector_size": record.vector_size or 2048,
        "document_count": record.document_count or 0,
        "chunk_count": record.chunk_count or 0,
        "status": record.status or "ready",
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _kb_source_snapshot(db: Session, source_name: str) -> dict[str, Any]:
    ks = KnowledgeSourceRepo.get(db, source_name)
    return {
        "source_name": ks.name,
        "collection_name": ks.collection_name,
        "vector_size": ks.vector_size,
        "embedding_model": ks.embedding_model or "",
    }


def _resolve_kb_names(req: CreateAgentRequest | UpdateAgentRequest, record: Agent | None = None) -> list[str]:
    names: list[str] = []
    if hasattr(req, "knowledge_base_names") and req.knowledge_base_names is not None:
        names = list(req.knowledge_base_names)
    elif getattr(req, "knowledge_base_name", None):
        names = [req.knowledge_base_name]  # type: ignore
    elif record and record.knowledge_base_names:
        names = list(record.knowledge_base_names)
    elif record and record.knowledge_base_name:
        names = [record.knowledge_base_name]
    return names


def _resolve_system_prompt(db: Session, req: CreateAgentRequest) -> str:
    if req.prompt_template_id:
        system_prompt, _ = PromptTemplateRepo.resolve_prompt(
            db, req.prompt_template_id, req.prompt_version, DEFAULT_SYSTEM_PROMPT
        )
        return system_prompt
    return req.system_prompt or DEFAULT_SYSTEM_PROMPT


class KnowledgeSourceRepo:
    @staticmethod
    def list_all(db: Session) -> list[KnowledgeSource]:
        return db.query(KnowledgeSource).order_by(KnowledgeSource.name).all()

    @staticmethod
    def get(db: Session, name: str) -> KnowledgeSource:
        record = db.query(KnowledgeSource).filter(KnowledgeSource.name == name).first()
        if not record:
            raise KnowledgeSourceNotFoundError(f"Knowledge source '{name}' not found")
        return record

    @staticmethod
    def create(db: Session, req: CreateKnowledgeSourceRequest) -> KnowledgeSource:
        if db.query(KnowledgeSource).filter(KnowledgeSource.name == req.name).first():
            raise ValueError(f"Knowledge source '{req.name}' already exists")
        collection_name = req.collection_name or slugify_name(req.name)
        record = KnowledgeSource(
            name=req.name,
            description=req.description,
            collection_name=collection_name,
            pipeline_id=req.pipeline,
            status="ready",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def delete(db: Session, name: str) -> KnowledgeSource:
        record = KnowledgeSourceRepo.get(db, name)
        db.delete(record)
        db.commit()
        return record

    @staticmethod
    def increment_counts(
        db: Session,
        name: str,
        document_count: int,
        chunk_count: int,
        status: str = "ready",
    ) -> KnowledgeSource:
        record = KnowledgeSourceRepo.get(db, name)
        record.document_count = (record.document_count or 0) + document_count
        record.chunk_count = (record.chunk_count or 0) + chunk_count
        record.status = status
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def set_status(db: Session, name: str, status: str) -> KnowledgeSource:
        record = KnowledgeSourceRepo.get(db, name)
        record.status = status
        db.commit()
        db.refresh(record)
        return record


class KnowledgeBaseRepo:
    @staticmethod
    def list_all(db: Session) -> list[KnowledgeBase]:
        return db.query(KnowledgeBase).order_by(KnowledgeBase.name).all()

    @staticmethod
    def get(db: Session, name: str) -> KnowledgeBase:
        record = db.query(KnowledgeBase).filter(KnowledgeBase.name == name).first()
        if not record:
            raise KnowledgeBaseNotFoundError(f"Knowledge base '{name}' not found")
        return record

    @staticmethod
    def create(db: Session, req: CreateKnowledgeBaseRequest) -> KnowledgeBase:
        if db.query(KnowledgeBase).filter(KnowledgeBase.name == req.name).first():
            raise ValueError(f"Knowledge base '{req.name}' already exists")
        sources = [_kb_source_snapshot(db, n) for n in req.source_names]
        record = KnowledgeBase(
            name=req.name,
            description=req.description,
            sources=sources,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def update(db: Session, name: str, req: UpdateKnowledgeBaseRequest) -> KnowledgeBase:
        record = KnowledgeBaseRepo.get(db, name)
        if req.description is not None:
            record.description = req.description
        if req.source_names is not None:
            record.sources = [_kb_source_snapshot(db, n) for n in req.source_names]
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def delete(db: Session, name: str) -> None:
        record = KnowledgeBaseRepo.get(db, name)
        db.delete(record)
        db.commit()

    @staticmethod
    def add_source(db: Session, kb_name: str, source_name: str) -> KnowledgeBase:
        record = KnowledgeBaseRepo.get(db, kb_name)
        snapshot = _kb_source_snapshot(db, source_name)
        sources = list(record.sources or [])
        if any(s.get("source_name") == source_name for s in sources):
            raise ValueError(f"Source '{source_name}' already in knowledge base")
        sources.append(snapshot)
        record.sources = sources
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def remove_source(db: Session, kb_name: str, source_name: str) -> KnowledgeBase:
        record = KnowledgeBaseRepo.get(db, kb_name)
        sources = [s for s in (record.sources or []) if s.get("source_name") != source_name]
        if len(sources) == len(record.sources or []):
            raise ValueError(f"Source '{source_name}' not in knowledge base")
        record.sources = sources
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def merge_collections(db: Session, kb_names: list[str]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        collections: list[dict[str, Any]] = []
        for kb_name in kb_names:
            kb = KnowledgeBaseRepo.get(db, kb_name)
            for src in kb.sources or []:
                col = src.get("collection_name", "")
                if col and col not in seen:
                    seen.add(col)
                    collections.append(src)
        return collections


def _validate_kb_embedding_consistency(db: Session, kb_names: list[str]) -> None:
    models: set[tuple[str, int]] = set()
    for kb_name in kb_names:
        kb = KnowledgeBaseRepo.get(db, kb_name)
        for src in kb.sources or []:
            models.add((src.get("embedding_model", ""), src.get("vector_size", 2048)))
    if len(models) > 1:
        raise ValueError(
            "All knowledge bases must use sources with the same embedding_model and vector_size"
        )


def _export_agent_yaml(agent: Agent) -> tuple[str | None, Any]:
    from rag_shared.agent_yaml import export_agent_record
    return export_agent_record(agent)


class AgentRepo:
    @staticmethod
    def list_all(db: Session) -> list[Agent]:
        return db.query(Agent).order_by(Agent.name).all()

    @staticmethod
    def get(db: Session, name: str) -> Agent:
        record = db.query(Agent).filter(Agent.name == name).first()
        if not record:
            raise AgentNotFoundError(f"Agent '{name}' not found")
        return record

    @staticmethod
    def _validate_create(db: Session, req: CreateAgentRequest) -> list[str]:
        kb_names = _resolve_kb_names(req)
        if req.knowledge_source_name and kb_names:
            raise ValueError("Set knowledge_base_names or knowledge_source_name, not both")
        if not kb_names and not req.knowledge_source_name:
            raise ValueError("Agent must reference at least one knowledge base or a knowledge source")
        for kb_name in kb_names:
            KnowledgeBaseRepo.get(db, kb_name)
        if kb_names:
            _validate_kb_embedding_consistency(db, kb_names)
        if req.knowledge_source_name:
            KnowledgeSourceRepo.get(db, req.knowledge_source_name)
        if req.prompt_template_id:
            try:
                PromptTemplateRepo.get(db, req.prompt_template_id)
            except PromptTemplateNotFoundError as e:
                raise ValueError(str(e)) from e
        return kb_names

    @staticmethod
    def create(db: Session, req: CreateAgentRequest) -> Agent:
        if db.query(Agent).filter(Agent.name == req.name).first():
            raise ValueError(f"Agent '{req.name}' already exists")
        kb_names = AgentRepo._validate_create(db, req)
        system_prompt = _resolve_system_prompt(db, req)
        record = Agent(
            name=req.name,
            description=req.description,
            knowledge_base_names=kb_names,
            knowledge_base_name=kb_names[0] if len(kb_names) == 1 else None,
            knowledge_source_name=req.knowledge_source_name,
            prompt_template_id=req.prompt_template_id,
            prompt_version=req.prompt_version,
            llm_model=req.llm_model,
            system_prompt=system_prompt,
            retrieval_strategy=req.retrieval_strategy,
            top_k=req.top_k,
            reranking_strategy=req.reranking_strategy,
            response_strategy=req.response_strategy,
            retrieval_config=req.retrieval_config or {},
            reranking_config=req.reranking_config or {},
            response_config=req.response_config or {},
            query_stages=req.query_stages or {},
            is_active=req.is_active,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        yaml_hash, exported_at = _export_agent_yaml(record)
        if yaml_hash:
            record.yaml_hash = yaml_hash
            record.yaml_exported_at = exported_at
            db.commit()
            db.refresh(record)
        return record

    @staticmethod
    def update(db: Session, name: str, req: UpdateAgentRequest) -> Agent:
        record = AgentRepo.get(db, name)
        if req.description is not None:
            record.description = req.description
        if req.knowledge_base_names is not None:
            for kb_name in req.knowledge_base_names:
                KnowledgeBaseRepo.get(db, kb_name)
            _validate_kb_embedding_consistency(db, req.knowledge_base_names)
            record.knowledge_base_names = req.knowledge_base_names
            record.knowledge_base_name = (
                req.knowledge_base_names[0] if len(req.knowledge_base_names) == 1 else None
            )
            record.knowledge_source_name = None
        if req.knowledge_base_name is not None:
            KnowledgeBaseRepo.get(db, req.knowledge_base_name)
            record.knowledge_base_name = req.knowledge_base_name
            record.knowledge_base_names = [req.knowledge_base_name]
            record.knowledge_source_name = None
        if req.knowledge_source_name is not None:
            KnowledgeSourceRepo.get(db, req.knowledge_source_name)
            record.knowledge_source_name = req.knowledge_source_name
            record.knowledge_base_names = []
            record.knowledge_base_name = None
        if req.prompt_template_id is not None:
            PromptTemplateRepo.get(db, req.prompt_template_id)
            record.prompt_template_id = req.prompt_template_id
        if req.prompt_version is not None:
            record.prompt_version = req.prompt_version
        if req.llm_model is not None:
            record.llm_model = req.llm_model
        if req.system_prompt is not None:
            record.system_prompt = req.system_prompt
        if req.prompt_template_id is not None or req.prompt_version is not None:
            record.system_prompt = PromptTemplateRepo.resolve_prompt(
                db,
                record.prompt_template_id,
                record.prompt_version,
                record.system_prompt,
            )[0]
        if req.retrieval_strategy is not None:
            record.retrieval_strategy = req.retrieval_strategy
        if req.top_k is not None:
            record.top_k = req.top_k
        if req.reranking_strategy is not None:
            record.reranking_strategy = req.reranking_strategy
        if req.response_strategy is not None:
            record.response_strategy = req.response_strategy
        if req.retrieval_config is not None:
            record.retrieval_config = req.retrieval_config
        if req.reranking_config is not None:
            record.reranking_config = req.reranking_config
        if req.response_config is not None:
            record.response_config = req.response_config
        if req.query_stages is not None:
            record.query_stages = req.query_stages
        if req.is_active is not None:
            record.is_active = req.is_active
        db.commit()
        db.refresh(record)
        yaml_hash, exported_at = _export_agent_yaml(record)
        if yaml_hash:
            record.yaml_hash = yaml_hash
            record.yaml_exported_at = exported_at
            db.commit()
            db.refresh(record)
        return record

    @staticmethod
    def delete(db: Session, name: str) -> None:
        record = AgentRepo.get(db, name)
        db.delete(record)
        db.commit()
