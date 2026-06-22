"""Evaluation metrics for embedding stage."""

from __future__ import annotations
import math
import random
import statistics
from typing import List, Dict, Any
from core.base_strategies import EmbeddingVector


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def evaluate_embeddings(embeddings: List[EmbeddingVector]) -> Dict[str, Any]:
    """
    Calculate embedding quality metrics.

    Args:
        embeddings: List of EmbeddingVector objects (chunk + vector).

    Returns:
        Dict with:
        - total_embeddings (int)
        - embedding_dimensions (int)
        - avg_vector_norm (float)
        - norm_stdev (float)
        - avg_cosine_similarity (float) — sampled to avoid O(n²)
        - dimension_utilization (float 0-1)
        - zero_vector_rate (float 0-1)
    """
    if not embeddings:
        return {
            "total_embeddings": 0,
            "embedding_dimensions": 0,
            "avg_vector_norm": 0.0,
            "norm_stdev": 0.0,
            "avg_cosine_similarity": 0.0,
            "dimension_utilization": 0.0,
            "zero_vector_rate": 0.0,
        }

    total_embeddings = len(embeddings)
    vectors = [e.vector for e in embeddings]
    embedding_dimensions = len(vectors[0]) if vectors else 0

    norms = [math.sqrt(sum(v * v for v in vec)) for vec in vectors]
    avg_vector_norm = statistics.mean(norms) if norms else 0.0
    norm_stdev = statistics.stdev(norms) if len(norms) > 1 else 0.0

    zero_vector_count = sum(1 for n in norms if n == 0.0)
    zero_vector_rate = zero_vector_count / total_embeddings if total_embeddings > 0 else 0.0

    # Dimension utilization
    dimension_utilization = 0.0
    if embedding_dimensions > 0 and total_embeddings > 1:
        dim_variances = []
        for dim_idx in range(embedding_dimensions):
            dim_values = [vec[dim_idx] for vec in vectors]
            dim_variances.append(statistics.variance(dim_values))
        utilized = sum(1 for var in dim_variances if var > 1e-10)
        dimension_utilization = utilized / embedding_dimensions

    # Average cosine similarity (sampled for large corpora)
    max_pairs = 100
    if total_embeddings <= 20:
        pairs = [(i, j) for i in range(total_embeddings) for j in range(i + 1, total_embeddings)]
    else:
        pairs = []
        for _ in range(max_pairs):
            i = random.randint(0, total_embeddings - 1)
            j = random.randint(0, total_embeddings - 1)
            if i != j:
                pairs.append((i, j))

    similarities = [_cosine_similarity(vectors[i], vectors[j]) for i, j in pairs]
    avg_cosine_similarity = statistics.mean(similarities) if similarities else 0.0

    return {
        "total_embeddings": total_embeddings,
        "embedding_dimensions": embedding_dimensions,
        "avg_vector_norm": avg_vector_norm,
        "norm_stdev": norm_stdev,
        "avg_cosine_similarity": avg_cosine_similarity,
        "dimension_utilization": dimension_utilization,
        "zero_vector_rate": zero_vector_rate,
    }