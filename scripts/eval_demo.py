#!/usr/bin/env python3
"""
Demo script for ingestion pipeline evaluation.
Run from: rag-ingestion-manager/ directory
Usage:  ./venv/bin/python ../scripts/eval_demo.py
"""

import json
import os
import sys

# Ensure the rag-ingestion-manager directory is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag-ingestion-manager"))

from core.base_strategies import Document, Chunk, EmbeddingVector
from evaluation import extraction_metrics, chunking_metrics, embedding_metrics, pipeline_health, runner


def demo_evaluation():
    """Run a complete evaluation with sample data."""
    print("🚀 Starting evaluation demo...")

    # --- Sample data -----------------------------------------------------------
    documents = [
        Document(id="doc1", content="This is the first test document with some content.", filename="test1.txt"),
        Document(id="doc2", content="This is the second test document with more content for evaluation.", filename="test2.pdf"),
        Document(id="doc3", content="", filename="empty.txt"),
    ]
    errors = [("failed.pdf", "Failed to extract due to unsupported format")]
    file_sizes_bytes = [1024, 2048, 512]
    stage_timings = {
        "ingestion": 0.25,
        "chunking": 0.15,
        "embedding": 0.30,
        "indexing": 0.20,
    }

    chunks = [
        Chunk(id="chunk1", document_id="doc1", content="First chunk of content.", chunk_index=0),
        Chunk(id="chunk2", document_id="doc1", content="Second chunk of content.", chunk_index=1),
        Chunk(id="chunk3", document_id="doc2", content="Chunk of second document.", chunk_index=0),
        Chunk(id="chunk4", document_id="doc2", content="Another chunk of second document.", chunk_index=1),
        Chunk(id="chunk5", document_id="doc3", content="", chunk_index=0),
    ]

    vectors = [
        [0.1, 0.2, 0.3, 0.4],
        [0.2, 0.3, 0.4, 0.5],
        [0.3, 0.4, 0.5, 0.6],
        [0.0, 0.0, 0.0, 0.0],
    ]
    embeddings = [
        EmbeddingVector(chunk=chunks[0], vector=vectors[0]),
        EmbeddingVector(chunk=chunks[1], vector=vectors[1]),
        EmbeddingVector(chunk=chunks[2], vector=vectors[2]),
        EmbeddingVector(chunk=chunks[3], vector=vectors[3]),
        EmbeddingVector(chunk=chunks[4], vector=[0.0, 0.0, 0.0, 0.0]),
    ]

    sync_result = {"added": 2, "updated": 0, "deleted": 0, "errors": errors}
    sync_duration = 0.60
    db_doc_count = 5
    db_chunk_count = 12

    # --- Run evaluation --------------------------------------------------------
    evaluation_result = runner.run_evaluation(
        collection_name="demo-collection",
        documents=documents,
        chunks=chunks,
        embeddings=embeddings,
        errors=errors,
        file_sizes_bytes=file_sizes_bytes,
        stage_timings=stage_timings,
        sync_result=sync_result,
        sync_duration=sync_duration,
        db_doc_count=db_doc_count,
        db_chunk_count=db_chunk_count,
        qdrant_client=None,
    )

    # --- Display results -------------------------------------------------------
    print("\n📊 Evaluation Results:")
    print(json.dumps(evaluation_result, indent=2, default=str))

    layers = evaluation_result.get("layers", {})
    print("\n🔎 Layer Details:")
    for layer_name, layer_data in layers.items():
        print(f"\n--- {layer_name.upper()} ---")
        if isinstance(layer_data, dict):
            for metric_name, metric_value in layer_data.items():
                print(f"  {metric_name}: {metric_value}")
        else:
            print(f"  {layer_data}")

    print("\n✅ Demo completed successfully!")


if __name__ == "__main__":
    demo_evaluation()