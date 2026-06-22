"""Evaluation package for the Multi-RAG ingestion pipeline."""

from .runner import run_evaluation
from .reporter import store_result, format_summary, compare_baseline
from .test_data import GoldenTestSet, TestQuestion
from .retrieval_eval import evaluate_retrieval

__all__ = [
    "run_evaluation",
    "store_result",
    "format_summary",
    "compare_baseline",
    "GoldenTestSet",
    "TestQuestion",
    "evaluate_retrieval",
]
