"""Orchestrates running all evaluation layers and collecting results."""

from __future__ import annotations
import time
from typing import Dict, Any, List, Tuple, Optional

from core.base_strategies import Document, Chunk, EmbeddingVector
from . import extraction_metrics, chunking_metrics, embedding_metrics, pipeline_health


def run_evaluation(
    collection_name: str,
    documents: List[Document],
    chunks: List[Chunk],
    embeddings: List[EmbeddingVector],
    errors: List[Tuple[str, str]],
    file_sizes_bytes: List[int],
    stage_timings: Dict[str, float],
    sync_result: Dict[str, Any],
    sync_duration: float,
    db_doc_count: int,
    db_chunk_count: int,
    qdrant_client: Optional[Any] = None,
    chunking_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run all evaluation layers and return a dict of results.

    Args:
        collection_name: Name of the collection being evaluated.
        documents: List of Document objects from the ingestion stage.
        chunks: List of Chunk objects from the chunking stage.
        embeddings: List of EmbeddingVector objects from the embedding stage.
        errors: List of (filename, error_message) tuples from ingestion.
        file_sizes_bytes: List of file sizes in bytes for each successfully ingested document.
        stage_timings: Dict of stage names to duration in seconds.
        sync_result: The result dict from the sync operation.
        sync_duration: Total time for the sync in seconds.
        db_doc_count: Total documents in DB for the collection after sync.
        db_chunk_count: Total chunks in DB for the collection after sync.
        qdrant_client: Optional QdrantClient instance for cross-validation.
        chunking_config: Optional chunking config dict (chunk_size, overlap, etc.).

    Returns:
        {
            "collection_name": str,
            "timestamp": float,
            "layers": {
                "extraction": {...},
                "chunking": {...},
                "embedding": {...},
                "pipeline": {...},
            }
        }
    """
    # Layer 1: Extraction metrics
    extraction_result = extraction_metrics.collect_extraction_stats(
        documents=documents,
        errors=errors,
        durations_ms=[t * 1000 for t in stage_timings.values()],
        file_sizes_bytes=file_sizes_bytes,
    )

    # Layer 2: Chunking metrics
    chunking_result = chunking_metrics.evaluate_chunks(
        chunks=chunks,
        chunking_config=chunking_config or {},
    )

    # Layer 3: Embedding metrics
    embedding_result = embedding_metrics.evaluate_embeddings(embeddings=embeddings)

    # Layer 4: Pipeline health
    pipeline_result = pipeline_health.collect_pipeline_stats(
        sync_result=sync_result,
        sync_duration=sync_duration,
        db_doc_count=db_doc_count,
        db_chunk_count=db_chunk_count,
    )
    if qdrant_client is not None:
        pipeline_result["qdrant_validation"] = pipeline_health.cross_validate_qdrant(
            qdrant_client=qdrant_client,
            collection_name=collection_name,
            db_chunk_count=db_chunk_count,
        )

    return {
        "collection_name": collection_name,
        "timestamp": time.time(),
        "layers": {
            "extraction": extraction_result,
            "chunking": chunking_result,
            "embedding": embedding_result,
            "pipeline": pipeline_result,
        },
    }