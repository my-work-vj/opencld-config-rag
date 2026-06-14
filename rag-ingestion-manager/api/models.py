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
    pipeline: str = Field("default_rag", description="Pipeline ID from shared database")


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
    pipeline_count: int
    collections: list[str]
