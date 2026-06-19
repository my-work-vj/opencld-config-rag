"""Pydantic models for ingestion API."""

from pydantic import BaseModel, Field
from typing import Any, Optional


class PipelineInfo(BaseModel):
    name: str
    description: str
    stages: dict[str, Any]


class PipelineList(BaseModel):
    pipelines: list[PipelineInfo]


class IngestRequest(BaseModel):
    source: str = Field(..., description="File path, directory path, URL, or raw text")
    source_type: str = Field("auto", description="auto, text, pdf, web")
    collection: Optional[str] = Field(
        None,
        description="Collection name — uses its ingestion stage config when set",
    )


class IngestResponse(BaseModel):
    document_count: int
    chunk_count: int
    embedding_count: int
    pipeline: str
    pipeline_name: str = ""
    collection_name: str
    status: str
    timings: dict[str, float]


class StatusResponse(BaseModel):
    status: str
    llm_available: bool
    qdrant_available: bool
    postgres_available: bool
    pathway_docker_ready: bool = False
    pathway_docker_message: str = ""
    pipeline_count: int
    collections: list[str]
    knowledge_source_count: int = 0
    knowledge_base_count: int = 0
    agent_count: int = 0


class PathwayDockerHealthResponse(BaseModel):
    docker_available: bool
    docker_message: str
    image: str
    image_present: bool
    container_name: str
    container_running: bool
    container_status: str
    ready: bool
    message: str
