"""Knowledge Base and Agent API routes — query manager."""

import logging

from fastapi import APIRouter, HTTPException

from core.db import SessionLocal
from core.models import QueryLog
from core.agent_runner import run_agent_query
from rag_shared.db import SessionLocal as SharedSession
from rag_shared.knowledge_repo import (
    AgentNotFoundError,
    AgentRepo,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseRepo,
    KnowledgeSourceNotFoundError,
    KnowledgeSourceRepo,
)
from rag_shared.agent_yaml import seed_from_directory as seed_agent_pipelines
from rag_shared.schemas import (
    AgentInfo,
    AgentList,
    AgentQueryRequest,
    AgentQueryResponse,
    CreateAgentRequest,
    CreateKnowledgeBaseRequest,
    KnowledgeBaseInfo,
    KnowledgeBaseList,
    KnowledgeSourceInfo,
    KnowledgeSourceList,
    UpdateAgentRequest,
    UpdateKnowledgeBaseRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _kb_info(record) -> KnowledgeBaseInfo:
    return KnowledgeBaseInfo(
        id=record.id,
        name=record.name,
        description=record.description or "",
        sources=record.sources or [],
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


def _agent_info(record) -> AgentInfo:
    kb_names = list(record.knowledge_base_names or [])
    if not kb_names and record.knowledge_base_name:
        kb_names = [record.knowledge_base_name]
    return AgentInfo(
        id=record.id,
        name=record.name,
        description=record.description or "",
        knowledge_base_names=kb_names,
        knowledge_base_name=record.knowledge_base_name,
        knowledge_source_name=record.knowledge_source_name,
        prompt_template_id=record.prompt_template_id,
        prompt_version=record.prompt_version,
        llm_model=record.llm_model,
        system_prompt=record.system_prompt or "",
        retrieval_strategy=record.retrieval_strategy,
        top_k=record.top_k,
        reranking_strategy=record.reranking_strategy,
        response_strategy=record.response_strategy or "contextual_response",
        retrieval_config=record.retrieval_config or {},
        reranking_config=record.reranking_config or {},
        response_config=record.response_config or {},
        query_stages=record.query_stages or {},
        is_active=bool(record.is_active),
        yaml_exported_at=record.yaml_exported_at.isoformat() if record.yaml_exported_at else None,
        yaml_hash=record.yaml_hash,
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


def _source_info(record) -> KnowledgeSourceInfo:
    return KnowledgeSourceInfo(
        id=record.id,
        name=record.name,
        description=record.description or "",
        collection_name=record.collection_name,
        pipeline_id=record.pipeline_id,
        embedding_model=record.embedding_model or "",
        vector_size=record.vector_size or 2048,
        document_count=record.document_count or 0,
        chunk_count=record.chunk_count or 0,
        status=record.status or "ready",
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


@router.get("/knowledge-sources", response_model=KnowledgeSourceList)
async def list_knowledge_sources():
    """Read-only list for KB UI — sources are created via ingestion service."""
    db = SharedSession()
    try:
        records = KnowledgeSourceRepo.list_all(db)
        return KnowledgeSourceList(sources=[_source_info(r) for r in records])
    finally:
        db.close()


# ── Knowledge Base ──


@router.post("/knowledge-bases", response_model=KnowledgeBaseInfo, status_code=201)
async def create_knowledge_base(req: CreateKnowledgeBaseRequest):
    db = SharedSession()
    try:
        record = KnowledgeBaseRepo.create(db, req)
        return _kb_info(record)
    except (ValueError, KnowledgeSourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@router.get("/knowledge-bases", response_model=KnowledgeBaseList)
async def list_knowledge_bases():
    db = SharedSession()
    try:
        records = KnowledgeBaseRepo.list_all(db)
        return KnowledgeBaseList(knowledge_bases=[_kb_info(r) for r in records])
    finally:
        db.close()


@router.get("/knowledge-bases/{name}", response_model=KnowledgeBaseInfo)
async def get_knowledge_base(name: str):
    db = SharedSession()
    try:
        record = KnowledgeBaseRepo.get(db, name)
        return _kb_info(record)
    except KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


@router.put("/knowledge-bases/{name}", response_model=KnowledgeBaseInfo)
async def update_knowledge_base(name: str, req: UpdateKnowledgeBaseRequest):
    db = SharedSession()
    try:
        record = KnowledgeBaseRepo.update(db, name, req)
        return _kb_info(record)
    except KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValueError, KnowledgeSourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@router.delete("/knowledge-bases/{name}", status_code=204)
async def delete_knowledge_base(name: str):
    db = SharedSession()
    try:
        KnowledgeBaseRepo.delete(db, name)
    except KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


@router.post("/knowledge-bases/{name}/sources/{source_name}", response_model=KnowledgeBaseInfo)
async def add_kb_source(name: str, source_name: str):
    db = SharedSession()
    try:
        record = KnowledgeBaseRepo.add_source(db, name, source_name)
        return _kb_info(record)
    except KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValueError, KnowledgeSourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@router.delete("/knowledge-bases/{name}/sources/{source_name}", response_model=KnowledgeBaseInfo)
async def remove_kb_source(name: str, source_name: str):
    db = SharedSession()
    try:
        record = KnowledgeBaseRepo.remove_source(db, name, source_name)
        return _kb_info(record)
    except KnowledgeBaseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


# ── Agents ──


@router.post("/agents", response_model=AgentInfo, status_code=201)
async def create_agent(req: CreateAgentRequest):
    db = SharedSession()
    try:
        record = AgentRepo.create(db, req)
        return _agent_info(record)
    except (ValueError, KnowledgeBaseNotFoundError, KnowledgeSourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@router.get("/agents", response_model=AgentList)
async def list_agents():
    db = SharedSession()
    try:
        records = AgentRepo.list_all(db)
        return AgentList(agents=[_agent_info(r) for r in records])
    finally:
        db.close()


@router.get("/agents/{name}", response_model=AgentInfo)
async def get_agent(name: str):
    db = SharedSession()
    try:
        record = AgentRepo.get(db, name)
        return _agent_info(record)
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


@router.put("/agents/{name}", response_model=AgentInfo)
async def update_agent(name: str, req: UpdateAgentRequest):
    db = SharedSession()
    try:
        record = AgentRepo.update(db, name, req)
        return _agent_info(record)
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValueError, KnowledgeBaseNotFoundError, KnowledgeSourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@router.delete("/agents/{name}", status_code=204)
async def delete_agent(name: str):
    db = SharedSession()
    try:
        AgentRepo.delete(db, name)
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


@router.post("/agents/{name}/query", response_model=AgentQueryResponse)
async def query_agent(name: str, req: AgentQueryRequest):
    result = run_agent_query(name, req.query, top_k_override=req.top_k)

    try:
        db = SessionLocal()
        log = QueryLog(
            pipeline_name=f"agent:{name}",
            collection_name=",".join(result.sources_searched),
            query=req.query,
            retrieval_method=result.retrieval_method,
            top_k=req.top_k if req.top_k is not None else 5,
            response=result.response[:500],
            retrieval_time_ms=result.timings.get("retrieval", 0) * 1000,
            reranking_time_ms=result.timings.get("reranking", 0) * 1000,
            response_time_ms=result.timings.get("response", 0) * 1000,
            total_time_ms=result.total_time_ms,
            chunk_count=len(result.chunks),
        )
        db.add(log)
        db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Could not log agent query: {e}")

    return result


@router.post("/agents/seed")
async def seed_agents(dry_run: bool = False):
    db = SharedSession()
    try:
        ids = seed_agent_pipelines(db, dry_run=dry_run)
        return {"seeded": ids, "count": len(ids), "dry_run": dry_run}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
