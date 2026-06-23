"""
Evaluate a collection by reading existing data from Qdrant and the DB.
This is used by the Evaluate button in the UI — it doesn't re-ingest files,
but evaluates the data already in the vector store.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _normalize_thresholds(threshold_result: dict) -> dict:
    """Convert nested threshold results into flat array format the frontend expects.

    Input (from check_thresholds):
        {
            "status": "pass",
            "results": {
                "extraction": {
                    "success_rate": {"value": 1.0, "threshold": {...}, "passed": true, ...},
                    ...
                },
                ...
            },
            "failures": [...]
        }

    Output:
        {
            "status": "pass",
            "results": [  # flat array
                {"layer": "extraction", "metric": "success_rate", "value": 1.0,
                 "threshold": {min/max}, "passed": true},
                ...
            ],
            "failures": [...],
            "summary": {"total": N, "passed": N, "failed": N},
            "all_passed": true
        }
    """
    results_dict = threshold_result.get("results", {})
    failures = threshold_result.get("failures", [])

    flat_results = []
    if isinstance(results_dict, dict):
        for layer_name, metrics in results_dict.items():
            if isinstance(metrics, dict):
                for metric_name, check in metrics.items():
                    if isinstance(check, dict):
                        # Build threshold display value
                        thresh = check.get("threshold", {})
                        if isinstance(thresh, dict):
                            # Show min/max as string like "≥0.95" or "≤0.1"
                            display_threshold = thresh
                        else:
                            display_threshold = thresh

                        flat_results.append({
                            "layer": layer_name,
                            "metric": metric_name,
                            "value": check.get("value"),
                            "threshold": thresh,
                            "passed": check.get("passed", False),
                        })

    total_checks = len(flat_results)
    passed_count = sum(1 for r in flat_results if r["passed"])
    threshold_result["results"] = flat_results
    threshold_result["summary"] = {
        "total": total_checks,
        "passed": passed_count,
        "failed": total_checks - passed_count,
    }
    threshold_result["all_passed"] = len(failures) == 0
    return threshold_result


def evaluate_collection_from_storage(
    collection_name: str,
    qdrant_collection_name: str | None = None,
) -> dict[str, Any]:
    """
    Collect evaluation data from Qdrant and DB for an existing collection
    and run the standard evaluation pipeline on it.

    Returns the full evaluation result with layers and thresholds.
    """
    # --- Lazy imports to avoid circular deps ---
    from qdrant_client import QdrantClient

    from rag_shared.db import SessionLocal as SharedSession
    from rag_shared.indexed_document_repo import IndexedDocumentRepo
    from rag_shared.knowledge_repo import KnowledgeSourceRepo
    from core.base_strategies import Document, Chunk, EmbeddingVector
    from evaluation.runner import run_evaluation
    from evaluation.reporter import store_result
    from evaluation.thresholds import check_thresholds

    # --- 1. Discover Qdrant collection name ---
    db = SharedSession()
    try:
        ks = KnowledgeSourceRepo.get(db, collection_name)
        if not ks:
            raise ValueError(f"Collection '{collection_name}' not found in DB")
        qdrant_name = qdrant_collection_name or ks.collection_name
        qdrant_collection = qdrant_name
    finally:
        db.close()

    # --- 2. Connect to Qdrant ---
    qdrant_host = os.environ.get("QDRANT_HOST", "host.docker.internal")
    qdrant_port = int(os.environ.get("QDRANT_PORT", "6333"))
    client = QdrantClient(host=qdrant_host, port=qdrant_port)

    # Validate collection exists
    try:
        col_info = client.get_collection(qdrant_collection)
    except Exception as exc:
        raise ValueError(f"Qdrant collection '{qdrant_collection}' not found: {exc}")

    total_points = col_info.points_count

    # --- 3. Scroll all points from Qdrant ---
    points: list[Any] = []
    next_offset = None
    batch_size = 100
    while True:
        batch, next_offset = client.scroll(
            collection_name=qdrant_collection,
            limit=batch_size,
            offset=next_offset,
            with_payload=True,
            with_vectors=True,
        )
        points.extend(batch)
        if next_offset is None or next_offset == 0:
            break

    logger.info(
        "Scrolled %d points from Qdrant collection '%s'",
        len(points),
        qdrant_collection,
    )

    # --- 4. Build Document, Chunk, EmbeddingVector objects ---
    documents_map: dict[str, Document] = {}
    chunks: list[Chunk] = []
    embeddings: list[EmbeddingVector] = []
    errors: list[Tuple[str, str]] = []

    for pt in points:
        payload = pt.payload or {}
        doc_id = payload.get("document_id") or payload.get("doc_id") or str(pt.id)
        content = payload.get("content", "")
        filename = payload.get("filename") or f"point_{pt.id}"

        # Build/reuse Document
        if doc_id not in documents_map:
            documents_map[doc_id] = Document(
                id=doc_id,
                content=content,  # partial content, but good enough
                metadata={
                    "filename": filename,
                    "qdrant_collection": qdrant_collection,
                    "payload_keys": list(payload.keys()),
                },
                filename=filename,
            )

        chunk = Chunk(
            id=str(pt.id),
            document_id=doc_id,
            content=content,
            metadata=payload,
            filename=filename,
        )
        chunks.append(chunk)

        # Build EmbeddingVector (use the stored embedding)
        if hasattr(pt, "vector") and pt.vector:
            emb = EmbeddingVector(
                chunk=chunk,
                vector=pt.vector if isinstance(pt.vector, list) else pt.vector.tolist(),
            )
            embeddings.append(emb)
        else:
            errors.append((filename, "No vector found in Qdrant point"))

    documents = list(documents_map.values())
    file_size_bytes_list = [len(d.content.encode("utf-8")) for d in documents]

    logger.info(
        "Reconstructed %d documents, %d chunks, %d embeddings from Qdrant",
        len(documents),
        len(chunks),
        len(embeddings),
    )

    # --- 5. Get DB counts ---
    db = SharedSession()
    try:
        db_doc_count = IndexedDocumentRepo.count_for_collection(db, collection_name)
        db_chunk_count = IndexedDocumentRepo.sum_chunks(db, collection_name)
    except Exception:
        db_doc_count = len(documents)
        db_chunk_count = len(chunks)
    finally:
        db.close()

    # --- 6. Run evaluation ---
    eval_result = run_evaluation(
        collection_name=collection_name,
        documents=documents,
        chunks=chunks,
        embeddings=embeddings,
        errors=errors,
        file_sizes_bytes=file_size_bytes_list,
        stage_timings={},
        sync_result={
            "total_documents": len(documents),
            "total_chunks": len(chunks),
            "total_embeddings": len(embeddings),
            "status": "success",
            "qdrant_points": total_points,
        },
        sync_duration=0.0,
        db_doc_count=db_doc_count,
        db_chunk_count=db_chunk_count,
        qdrant_client=client,
    )

    # --- 7. Check thresholds and store report ---
    threshold_result = check_thresholds(eval_result)
    # Normalize threshold format for frontend
    threshold_result = _normalize_thresholds(threshold_result)

    eval_result["thresholds"] = threshold_result

    # Normalize field names before storing so /latest returns correct format
    layers = eval_result.setdefault("layers", {})

    extraction = layers.get("extraction", {})
    if extraction:
        if "total_documents" not in extraction and "total_files_processed" in extraction:
            extraction["total_documents"] = extraction["total_files_processed"]

    chunking = layers.get("chunking", {})
    if chunking:
        if "p50" not in chunking and "chunk_size_p50" in chunking:
            chunking["p50"] = chunking["chunk_size_p50"]
        if "p95" not in chunking and "chunk_size_p95" in chunking:
            chunking["p95"] = chunking["chunk_size_p95"]
        if "p99" not in chunking and "chunk_size_p99" in chunking:
            chunking["p99"] = chunking["chunk_size_p99"]

    pipeline = layers.get("pipeline", {})
    if pipeline:
        if "total_documents" not in pipeline and "total_files_processed" in pipeline:
            pipeline["total_documents"] = pipeline["total_files_processed"]

    report_path = store_result(eval_result)

    logger.info(
        "Evaluation complete for '%s': thresholds %s, report at %s",
        collection_name,
        threshold_result.get("summary", {}),
        report_path,
    )

    eval_result["report_path"] = report_path

    return eval_result
