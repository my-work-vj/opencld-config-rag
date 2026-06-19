"""Prompt template API routes — query manager."""

import logging

from fastapi import APIRouter, HTTPException

from rag_shared.db import SessionLocal as SharedSession
from rag_shared.prompt_repo import PromptTemplateNotFoundError, PromptTemplateRepo
from rag_shared.prompt_seed import seed_from_directory
from rag_shared.schemas import (
    CreatePromptTemplateRequest,
    CreatePromptVersionRequest,
    PromptTemplateDetail,
    PromptTemplateList,
    PromptTemplateSummary,
    PromptVersionInfo,
    SetActiveVersionRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _version_info(v) -> PromptVersionInfo:
    return PromptVersionInfo(
        version=v.version,
        system_prompt=v.system_prompt,
        user_prompt_template=v.user_prompt_template or "",
        changelog=v.changelog or "",
        created_at=v.created_at.isoformat() if v.created_at else None,
    )


def _summary(db, template) -> PromptTemplateSummary:
    versions = PromptTemplateRepo.get_versions(db, template.id)
    active = next((v for v in versions if v.version == template.active_version), None)
    return PromptTemplateSummary(
        id=template.id,
        name=template.name,
        description=template.description or "",
        active_version=template.active_version or 1,
        active_system_prompt=(active.system_prompt[:120] + "...") if active and len(active.system_prompt) > 120 else (active.system_prompt if active else ""),
        version_count=len(versions),
        created_at=template.created_at.isoformat() if template.created_at else None,
    )


@router.post("/prompt-templates", status_code=201)
async def create_prompt_template(req: CreatePromptTemplateRequest):
    db = SharedSession()
    try:
        record = PromptTemplateRepo.create(db, req)
        versions = PromptTemplateRepo.get_versions(db, record.id)
        return PromptTemplateDetail(
            id=record.id,
            name=record.name,
            description=record.description or "",
            active_version=record.active_version or 1,
            versions=[_version_info(v) for v in versions],
            created_at=record.created_at.isoformat() if record.created_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    finally:
        db.close()


@router.get("/prompt-templates", response_model=PromptTemplateList)
async def list_prompt_templates():
    db = SharedSession()
    try:
        records = PromptTemplateRepo.list_all(db)
        return PromptTemplateList(templates=[_summary(db, r) for r in records])
    finally:
        db.close()


@router.get("/prompt-templates/{template_id}", response_model=PromptTemplateDetail)
async def get_prompt_template(template_id: str):
    db = SharedSession()
    try:
        record = PromptTemplateRepo.get(db, template_id)
        versions = PromptTemplateRepo.get_versions(db, template_id)
        return PromptTemplateDetail(
            id=record.id,
            name=record.name,
            description=record.description or "",
            active_version=record.active_version or 1,
            versions=[_version_info(v) for v in versions],
            created_at=record.created_at.isoformat() if record.created_at else None,
        )
    except PromptTemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


@router.post("/prompt-templates/{template_id}/versions", status_code=201)
async def add_prompt_version(template_id: str, req: CreatePromptVersionRequest):
    db = SharedSession()
    try:
        version = PromptTemplateRepo.add_version(db, template_id, req)
        return _version_info(version)
    except PromptTemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


@router.put("/prompt-templates/{template_id}/active-version")
async def set_active_version(template_id: str, req: SetActiveVersionRequest):
    db = SharedSession()
    try:
        record = PromptTemplateRepo.set_active_version(db, template_id, req)
        return {"id": record.id, "active_version": record.active_version}
    except PromptTemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@router.delete("/prompt-templates/{template_id}", status_code=204)
async def delete_prompt_template(template_id: str):
    db = SharedSession()
    try:
        PromptTemplateRepo.delete(db, template_id)
    except PromptTemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


@router.post("/prompt-templates/seed")
async def seed_prompt_templates(dry_run: bool = False):
    try:
        ids = seed_from_directory(dry_run=dry_run)
        return {"seeded": ids, "count": len(ids), "dry_run": dry_run}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
