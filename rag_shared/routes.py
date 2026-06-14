"""Shared FastAPI routes for pipeline CRUD (hybrid config layer)."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from rag_shared.db import SessionLocal
from rag_shared.loader import load_ingestion_config, load_query_config
from rag_shared.repo import PipelineNotFoundError, PipelineRepo
from rag_shared.schemas import (
    PipelineCreateRequest,
    PipelineListResponse,
    PipelineResponse,
    PipelineUpdateRequest,
)
from rag_shared.seed import seed_from_directory


def create_pipeline_router() -> APIRouter:
    router = APIRouter()

    @router.get("/pipelines", response_model=PipelineListResponse)
    async def list_pipelines(status: Optional[str] = Query(None)):
        db = SessionLocal()
        try:
            records = PipelineRepo.list_all(db, status=status)
            return PipelineListResponse(
                pipelines=[PipelineResponse.model_validate(r) for r in records],
                total=len(records),
            )
        finally:
            db.close()

    @router.post("/pipelines/seed")
    async def seed_pipelines(dry_run: bool = False):
        """Re-seed database from pipelines/*.yaml (admin/dev)."""
        try:
            ids = seed_from_directory(dry_run=dry_run)
            return {"seeded": ids, "count": len(ids), "dry_run": dry_run}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
    async def get_pipeline(pipeline_id: str):
        db = SessionLocal()
        try:
            record = PipelineRepo.get(db, pipeline_id)
            return PipelineResponse.model_validate(record)
        except PipelineNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        finally:
            db.close()

    @router.post("/pipelines", response_model=PipelineResponse, status_code=201)
    async def create_pipeline(req: PipelineCreateRequest):
        db = SessionLocal()
        try:
            record = PipelineRepo.create(db, req)
            return PipelineResponse.model_validate(record)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        finally:
            db.close()

    @router.patch("/pipelines/{pipeline_id}", response_model=PipelineResponse)
    async def update_pipeline(pipeline_id: str, req: PipelineUpdateRequest):
        db = SessionLocal()
        try:
            record = PipelineRepo.update(db, pipeline_id, req)
            return PipelineResponse.model_validate(record)
        except PipelineNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        finally:
            db.close()

    @router.delete("/pipelines/{pipeline_id}", status_code=204)
    async def delete_pipeline(pipeline_id: str):
        db = SessionLocal()
        try:
            PipelineRepo.delete(db, pipeline_id)
        except PipelineNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        finally:
            db.close()

    @router.get("/pipelines/{pipeline_id}/resolved/ingestion")
    async def preview_ingestion_config(pipeline_id: str):
        db = SessionLocal()
        try:
            return load_ingestion_config(db, pipeline_id)
        except PipelineNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        finally:
            db.close()

    @router.get("/pipelines/{pipeline_id}/resolved/query")
    async def preview_query_config(pipeline_id: str):
        db = SessionLocal()
        try:
            return load_query_config(db, pipeline_id)
        except PipelineNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        finally:
            db.close()

    return router
