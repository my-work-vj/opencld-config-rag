"""Pipeline configuration repository — database CRUD."""

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from rag_shared.models import RagPipeline, RagPipelineAudit
from rag_shared.schemas import (
    PipelineCreateRequest,
    PipelineUpdateRequest,
    PipelineYamlDocument,
)

logger = logging.getLogger(__name__)


class PipelineNotFoundError(Exception):
    pass


class PipelineRepo:
    @staticmethod
    def _to_dict(record: RagPipeline) -> dict[str, Any]:
        return {
            "id": record.id,
            "name": record.name,
            "description": record.description or "",
            "stages": record.stages or {},
            "embedding_model": record.embedding_model,
            "chat_model": record.chat_model,
            "reranker_model": record.reranker_model,
            "llm_params": record.llm_params or {},
            "status": record.status,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    @staticmethod
    def list_all(db: Session, status: Optional[str] = None) -> list[RagPipeline]:
        query = db.query(RagPipeline).order_by(RagPipeline.name)
        if status:
            query = query.filter(RagPipeline.status == status)
        return query.all()

    @staticmethod
    def get(db: Session, pipeline_id: str) -> RagPipeline:
        record = db.query(RagPipeline).filter(RagPipeline.id == pipeline_id).first()
        if not record:
            raise PipelineNotFoundError(f"Pipeline '{pipeline_id}' not found")
        return record

    @staticmethod
    def create(db: Session, req: PipelineCreateRequest, changed_by: str = "api") -> RagPipeline:
        if db.query(RagPipeline).filter(RagPipeline.id == req.id).first():
            raise ValueError(f"Pipeline '{req.id}' already exists")
        record = RagPipeline(
            id=req.id,
            name=req.name,
            description=req.description,
            stages={k: v.model_dump() for k, v in req.stages.items()},
            embedding_model=req.embedding_model,
            chat_model=req.chat_model,
            reranker_model=req.reranker_model,
            llm_params=req.llm_params,
            status=req.status,
        )
        db.add(record)
        db.flush()
        PipelineRepo._audit(db, req.id, {}, PipelineRepo._to_dict(record), changed_by)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def upsert_from_yaml(db: Session, doc: PipelineYamlDocument, changed_by: str = "seed") -> RagPipeline:
        stages = {k: v.model_dump() for k, v in doc.stages.items()}
        existing = db.query(RagPipeline).filter(RagPipeline.id == doc.id).first()
        old = PipelineRepo._to_dict(existing) if existing else {}

        if existing:
            existing.name = doc.name
            existing.description = doc.description
            existing.stages = stages
            existing.embedding_model = doc.embedding_model
            existing.chat_model = doc.chat_model
            existing.reranker_model = doc.reranker_model
            existing.llm_params = doc.llm_params
            existing.status = doc.status
            record = existing
        else:
            record = RagPipeline(
                id=doc.id,
                name=doc.name,
                description=doc.description,
                stages=stages,
                embedding_model=doc.embedding_model,
                chat_model=doc.chat_model,
                reranker_model=doc.reranker_model,
                llm_params=doc.llm_params,
                status=doc.status,
            )
            db.add(record)

        db.flush()
        PipelineRepo._audit(db, doc.id, old, PipelineRepo._to_dict(record), changed_by)
        db.commit()
        db.refresh(record)
        logger.info(f"Upserted pipeline '{doc.id}' from YAML")
        return record

    @staticmethod
    def update(
        db: Session,
        pipeline_id: str,
        req: PipelineUpdateRequest,
        changed_by: str = "api",
    ) -> RagPipeline:
        record = PipelineRepo.get(db, pipeline_id)
        old = PipelineRepo._to_dict(record)

        if req.name is not None:
            record.name = req.name
        if req.description is not None:
            record.description = req.description
        if req.stages is not None:
            record.stages = {k: v.model_dump() for k, v in req.stages.items()}
        if req.embedding_model is not None:
            record.embedding_model = req.embedding_model
        if req.chat_model is not None:
            record.chat_model = req.chat_model
        if req.reranker_model is not None:
            record.reranker_model = req.reranker_model
        if req.llm_params is not None:
            record.llm_params = req.llm_params
        if req.status is not None:
            record.status = req.status

        db.flush()
        PipelineRepo._audit(db, pipeline_id, old, PipelineRepo._to_dict(record), changed_by)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def delete(db: Session, pipeline_id: str, changed_by: str = "api") -> None:
        record = PipelineRepo.get(db, pipeline_id)
        old = PipelineRepo._to_dict(record)
        db.delete(record)
        PipelineRepo._audit(db, pipeline_id, old, {}, changed_by)
        db.commit()

    @staticmethod
    def _audit(
        db: Session,
        pipeline_id: str,
        old_config: dict,
        new_config: dict,
        changed_by: str,
    ) -> None:
        if old_config == new_config:
            return
        db.add(RagPipelineAudit(
            pipeline_id=pipeline_id,
            changed_by=changed_by,
            old_config=old_config,
            new_config=new_config,
        ))
