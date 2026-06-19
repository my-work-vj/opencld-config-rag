"""Prompt template repository."""

import logging
from typing import Any

from sqlalchemy.orm import Session

from rag_shared.models import PromptTemplate, PromptVersion
from rag_shared.schemas import (
    CreatePromptTemplateRequest,
    CreatePromptVersionRequest,
    SetActiveVersionRequest,
)
from rag_shared.yaml_export import export_prompt_template

logger = logging.getLogger(__name__)


class PromptTemplateNotFoundError(Exception):
    pass


class PromptVersionNotFoundError(Exception):
    pass


def _export_template(db: Session, template: PromptTemplate) -> None:
    versions = (
        db.query(PromptVersion)
        .filter(PromptVersion.template_id == template.id)
        .order_by(PromptVersion.version)
        .all()
    )
    version_docs = [
        {
            "version": v.version,
            "system_prompt": v.system_prompt,
            **({"user_prompt_template": v.user_prompt_template} if v.user_prompt_template else {}),
            **({"changelog": v.changelog} if v.changelog else {}),
        }
        for v in versions
    ]
    yaml_hash, exported_at = export_prompt_template(
        template_id=template.id,
        name=template.name,
        description=template.description or "",
        active_version=template.active_version or 1,
        versions=version_docs,
    )
    if yaml_hash:
        pass  # prompt templates export to disk only


class PromptTemplateRepo:
    @staticmethod
    def list_all(db: Session) -> list[PromptTemplate]:
        return db.query(PromptTemplate).order_by(PromptTemplate.id).all()

    @staticmethod
    def get(db: Session, template_id: str) -> PromptTemplate:
        record = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
        if not record:
            raise PromptTemplateNotFoundError(f"Prompt template '{template_id}' not found")
        return record

    @staticmethod
    def get_versions(db: Session, template_id: str) -> list[PromptVersion]:
        PromptTemplateRepo.get(db, template_id)
        return (
            db.query(PromptVersion)
            .filter(PromptVersion.template_id == template_id)
            .order_by(PromptVersion.version)
            .all()
        )

    @staticmethod
    def get_version(
        db: Session, template_id: str, version: int | None = None
    ) -> PromptVersion:
        template = PromptTemplateRepo.get(db, template_id)
        ver = version if version is not None else template.active_version
        record = (
            db.query(PromptVersion)
            .filter(PromptVersion.template_id == template_id, PromptVersion.version == ver)
            .first()
        )
        if not record:
            raise PromptVersionNotFoundError(
                f"Prompt version {ver} not found for template '{template_id}'"
            )
        return record

    @staticmethod
    def resolve_prompt(
        db: Session,
        template_id: str | None,
        version: int | None,
        fallback: str,
    ) -> tuple[str, str]:
        if not template_id:
            return fallback, ""
        pv = PromptTemplateRepo.get_version(db, template_id, version)
        return pv.system_prompt, pv.user_prompt_template or ""

    @staticmethod
    def create(db: Session, req: CreatePromptTemplateRequest) -> PromptTemplate:
        if db.query(PromptTemplate).filter(PromptTemplate.id == req.id).first():
            raise ValueError(f"Prompt template '{req.id}' already exists")
        template = PromptTemplate(
            id=req.id,
            name=req.name,
            description=req.description,
            active_version=1,
        )
        db.add(template)
        db.flush()
        version = PromptVersion(
            template_id=req.id,
            version=1,
            system_prompt=req.system_prompt,
            user_prompt_template=req.user_prompt_template or "",
            changelog=req.changelog or "Initial version",
        )
        db.add(version)
        db.commit()
        db.refresh(template)
        _export_template(db, template)
        return template

    @staticmethod
    def add_version(db: Session, template_id: str, req: CreatePromptVersionRequest) -> PromptVersion:
        template = PromptTemplateRepo.get(db, template_id)
        latest = (
            db.query(PromptVersion)
            .filter(PromptVersion.template_id == template_id)
            .order_by(PromptVersion.version.desc())
            .first()
        )
        next_ver = (latest.version + 1) if latest else 1
        version = PromptVersion(
            template_id=template_id,
            version=next_ver,
            system_prompt=req.system_prompt,
            user_prompt_template=req.user_prompt_template or "",
            changelog=req.changelog or f"Version {next_ver}",
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        _export_template(db, template)
        return version

    @staticmethod
    def set_active_version(
        db: Session, template_id: str, req: SetActiveVersionRequest
    ) -> PromptTemplate:
        template = PromptTemplateRepo.get(db, template_id)
        PromptTemplateRepo.get_version(db, template_id, req.version)
        template.active_version = req.version
        db.commit()
        db.refresh(template)
        _export_template(db, template)
        return template

    @staticmethod
    def delete(db: Session, template_id: str) -> None:
        template = PromptTemplateRepo.get(db, template_id)
        db.query(PromptVersion).filter(PromptVersion.template_id == template_id).delete()
        db.delete(template)
        db.commit()

    @staticmethod
    def upsert_from_yaml(db: Session, doc: dict[str, Any]) -> PromptTemplate:
        template_id = doc["id"]
        existing = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
        if existing:
            template = existing
            template.name = doc.get("name", template_id)
            template.description = doc.get("description", "")
            template.active_version = doc.get("active_version", 1)
            db.query(PromptVersion).filter(PromptVersion.template_id == template_id).delete()
        else:
            template = PromptTemplate(
                id=template_id,
                name=doc.get("name", template_id),
                description=doc.get("description", ""),
                active_version=doc.get("active_version", 1),
            )
            db.add(template)
        db.flush()
        for v in doc.get("versions", []):
            db.add(
                PromptVersion(
                    template_id=template_id,
                    version=v["version"],
                    system_prompt=v["system_prompt"],
                    user_prompt_template=v.get("user_prompt_template", ""),
                    changelog=v.get("changelog", ""),
                )
            )
        db.commit()
        db.refresh(template)
        return template
