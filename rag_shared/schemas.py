"""Pydantic schemas for pipeline configuration validation."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class StageConfig(BaseModel):
    strategy: str
    config: dict[str, Any] = Field(default_factory=dict)


class PipelineYamlDocument(BaseModel):
    """Validates a unified pipeline YAML file before seeding the database."""
    id: str
    name: str
    description: str = ""
    stages: dict[str, StageConfig]
    embedding_model: Optional[str] = None
    chat_model: Optional[str] = None
    reranker_model: Optional[str] = None
    llm_params: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"

    @field_validator("stages")
    @classmethod
    def stages_not_empty(cls, value: dict[str, StageConfig]) -> dict[str, StageConfig]:
        if not value:
            raise ValueError("stages must not be empty")
        return value


class PipelineCreateRequest(BaseModel):
    """Create a pipeline via API (UI-driven)."""
    id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$", min_length=1, max_length=255)
    name: str
    description: str = ""
    stages: dict[str, StageConfig]
    embedding_model: Optional[str] = None
    chat_model: Optional[str] = None
    reranker_model: Optional[str] = None
    llm_params: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"


class PipelineUpdateRequest(BaseModel):
    """Partial update of a pipeline."""
    name: Optional[str] = None
    description: Optional[str] = None
    stages: Optional[dict[str, StageConfig]] = None
    embedding_model: Optional[str] = None
    chat_model: Optional[str] = None
    reranker_model: Optional[str] = None
    llm_params: Optional[dict[str, Any]] = None
    status: Optional[str] = None


class PipelineResponse(BaseModel):
    id: str
    name: str
    description: str
    stages: dict[str, Any]
    embedding_model: Optional[str] = None
    chat_model: Optional[str] = None
    reranker_model: Optional[str] = None
    llm_params: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PipelineListResponse(BaseModel):
    pipelines: list[PipelineResponse]
    total: int
