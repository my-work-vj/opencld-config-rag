"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


class PipelineInfo(BaseModel):
    """Pipeline configuration summary."""
    name: str
    description: str
    stages: dict[str, Any]


class PipelineList(BaseModel):
    pipelines: list[PipelineInfo]


class IngestRequest(BaseModel):
    source: str = Field(..., description="File path, directory path, URL, or raw text")
    source_type: str = Field("auto", description="auto, text, pdf, web")
    pipeline: str = Field("default_pipeline", description="Pipeline config name")


class IngestResponse(BaseModel):
    document_count: int
    chunk_count: int
    embedding_count: int
    pipeline: str
    status: str


class QueryRequest(BaseModel):
    query: str = Field(..., description="The user query")
    pipeline: str = Field("default_pipeline", description="Pipeline config to use")
    top_k: Optional[int] = Field(5, description="Number of chunks to retrieve")
    retrieval_overrides: Optional[dict[str, Any]] = Field(None, description="Override retrieval config")
    reranking_overrides: Optional[dict[str, Any]] = Field(None, description="Override reranking config")
    response_overrides: Optional[dict[str, Any]] = Field(None, description="Override response config")


class ChunkResult(BaseModel):
    content: str
    score: float
    retrieval_method: str
    filename: Optional[str] = None
    chunk_index: int = 0


class QueryResponse(BaseModel):
    query: str
    pipeline: str
    response: str
    retrieval_method: str
    chunks: list[ChunkResult]
    timings: dict[str, float]
    total_time_ms: float


class StrategyInfo(BaseModel):
    stage: str
    strategies: list[str]


class CompareQueryRequest(BaseModel):
    query: str
    pipelines: list[str] = Field(default=["naive_rag", "vector_rag", "hybrid_bm25_vector"])
    top_k: Optional[int] = 5


class CompareResult(BaseModel):
    pipeline: str
    response: str
    chunk_count: int
    retrieval_method: str
    timings: dict[str, float]


class CompareResponse(BaseModel):
    query: str
    results: list[CompareResult]


class StatusResponse(BaseModel):
    status: str
    llm_available: bool
    qdrant_available: bool
    postgres_available: bool
    pipeline_count: int
    document_count: int
