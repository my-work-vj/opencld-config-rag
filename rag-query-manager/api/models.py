"""Pydantic models for query API."""

from pydantic import BaseModel, Field
from typing import Any, Optional


class PipelineInfo(BaseModel):
    name: str
    description: str
    stages: dict[str, Any]


class PipelineList(BaseModel):
    pipelines: list[PipelineInfo]


class QueryRequest(BaseModel):
    query: str = Field(..., description="The user query")
    pipeline: str = Field("default_rag", description="Pipeline ID from shared database")
    collection_name: Optional[str] = Field(None, description="Override Qdrant collection")
    top_k: Optional[int] = Field(5, description="Number of chunks to retrieve")
    knowledge_store_overrides: Optional[dict[str, Any]] = None
    retrieval_overrides: Optional[dict[str, Any]] = None
    reranking_overrides: Optional[dict[str, Any]] = None
    response_overrides: Optional[dict[str, Any]] = None


class ChunkResult(BaseModel):
    content: str
    score: float
    retrieval_method: str
    filename: Optional[str] = None
    chunk_index: int = 0


class QueryResponse(BaseModel):
    query: str
    pipeline: str
    pipeline_name: str = ""
    collection_name: str
    response: str
    retrieval_method: str
    chunks: list[ChunkResult]
    timings: dict[str, float]
    total_time_ms: float


class CompareQueryRequest(BaseModel):
    query: str
    pipelines: list[str] = Field(
        default=["naive_rag", "vector_rag", "hybrid_rag"]
    )
    collection_name: Optional[str] = None
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
    collections: list[str]
