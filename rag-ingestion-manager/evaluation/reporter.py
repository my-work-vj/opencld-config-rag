"""Formats, stores, and compares evaluation results."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Default storage directory for evaluation reports
DEFAULT_REPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "eval_reports",
)


def _timestamp_tag() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _report_path(collection_name: str, base_dir: str | None = None) -> Path:
    storage = Path(base_dir or DEFAULT_REPORT_DIR)
    coll_dir = storage / collection_name
    coll_dir.mkdir(parents=True, exist_ok=True)
    return coll_dir


def _latest_report(collection_name: str, base_dir: str | None = None) -> Optional[Path]:
    """Find the most recent report file for a collection."""
    coll_dir = _report_path(collection_name, base_dir)
    reports = sorted(coll_dir.glob("eval_*.json"), reverse=True)
    return reports[0] if reports else None


def store_result(result: Dict[str, Any], base_dir: str | None = None) -> str:
    """Persist an evaluation result to a JSON file.

    Returns the file path of the stored report.
    """
    collection_name = result.get("collection_name", "unknown")
    report_dir = _report_path(collection_name, base_dir)
    filename = f"eval_{_timestamp_tag()}.json"
    filepath = report_dir / filename

    # Strip raw data objects (Document/Chunk/EmbeddingVector) that can't be serialized
    safe_result = _make_serializable(result)

    with open(filepath, "w") as f:
        json.dump(safe_result, f, indent=2, default=str)

    return str(filepath)


def _make_serializable(obj: Any) -> Any:
    """Recursively convert non-serializable objects to strings."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return {k: _make_serializable(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, tuple):
        return [_make_serializable(v) for v in obj]
    # Primitive types that JSON can handle
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    # Fallback: convert to string
    return str(obj)


def format_summary(result: Dict[str, Any]) -> str:
    """Format evaluation results as human-readable markdown."""
    coll = result.get("collection_name", "?")
    ts = result.get("timestamp", 0)
    layers = result.get("layers", {})

    lines = [
        f"# Evaluation Report: `{coll}`",
        f"**Timestamp:** {datetime.utcfromtimestamp(ts).isoformat() if isinstance(ts, (int, float)) else ts}",
        "",
    ]

    # Layer 1: Extraction
    ext = layers.get("extraction", {})
    if ext:
        lines.extend([
            "## Layer 1: Extraction Quality",
            f"- **Success Rate:** {ext.get('success_rate', '?'):.1%}",
            f"- **Files Processed:** {ext.get('total_files', '?')}",
            f"- **Empty Extraction:** {ext.get('empty_extraction_rate', '?'):.1%}" if isinstance(ext.get('empty_extraction_rate'), (int, float)) else f"- **Empty Extraction:** {ext.get('empty_extraction_rate', '?')}",
            f"- **Error Rate:** {ext.get('error_rate', '?'):.1%}" if isinstance(ext.get('error_rate'), (int, float)) else f"- **Error Rate:** {ext.get('error_rate', '?')}",
            f"- **Avg Content Length:** {ext.get('avg_content_length', '?'):.0f} chars" if isinstance(ext.get('avg_content_length'), (int, float)) else f"- **Avg Content Length:** {ext.get('avg_content_length', '?')}",
            "",
        ])

    # Layer 2: Chunking
    chk = layers.get("chunking", {})
    if chk:
        lines.extend([
            "## Layer 2: Chunking Quality",
            f"- **Total Chunks:** {chk.get('total_chunks', '?')}",
            f"- **Avg Chunk Size:** {chk.get('avg_chunk_size', '?'):.0f} chars" if isinstance(chk.get('avg_chunk_size'), (int, float)) else f"- **Avg Chunk Size:** {chk.get('avg_chunk_size', '?')}",
            f"- **P50/P95/P99:** {chk.get('p50', '?')}/{chk.get('p95', '?')}/{chk.get('p99', '?')}",
            f"- **Empty Chunks:** {chk.get('empty_chunks', 0)}",
            f"- **Duplicate Rate:** {chk.get('duplicate_content_rate', '?'):.1%}" if isinstance(chk.get('duplicate_content_rate'), (int, float)) else f"- **Duplicate Rate:** {chk.get('duplicate_content_rate', '?')}",
            "",
        ])

    # Layer 3: Embedding
    emb = layers.get("embedding", {})
    if emb:
        lines.extend([
            "## Layer 3: Embedding Quality",
            f"- **Total Embeddings:** {emb.get('total_embeddings', '?')}",
            f"- **Dimensions:** {emb.get('embedding_dimensions', '?')}",
            f"- **Avg Vector Norm:** {emb.get('avg_vector_norm', '?'):.4f}",
            f"- **Zero Vector Rate:** {emb.get('zero_vector_rate', '?'):.1%}" if isinstance(emb.get('zero_vector_rate'), (int, float)) else f"- **Zero Vector Rate:** {emb.get('zero_vector_rate', '?')}",
            f"- **Dimension Utilization:** {emb.get('dimension_utilization', '?'):.1%}" if isinstance(emb.get('dimension_utilization'), (int, float)) else f"- **Dimension Utilization:** {emb.get('dimension_utilization', '?')}",
            "",
        ])

    # Layer 4: Pipeline
    pip = layers.get("pipeline", {})
    if pip:
        lines.extend([
            "## Layer 4: Pipeline Health",
            f"- **Status:** {pip.get('status', '?')}",
            f"- **Files Added/Updated/Deleted:** {pip.get('files_added', 0)}/{pip.get('files_updated', 0)}/{pip.get('files_deleted', 0)}",
            f"- **Total Documents:** {pip.get('total_documents', '?')}",
            f"- **Total Chunks:** {pip.get('total_chunks', '?')}",
            f"- **Docs/Second:** {pip.get('docs_per_second', '?'):.2f}" if isinstance(pip.get('docs_per_second'), (int, float)) else f"- **Docs/Second:** {pip.get('docs_per_second', '?')}",
            f"- **Error Rate:** {pip.get('error_rate', '?'):.1%}" if isinstance(pip.get('error_rate'), (int, float)) else f"- **Error Rate:** {pip.get('error_rate', '?')}",
            "",
        ])
        qv = pip.get("qdrant_validation")
        if qv:
            in_sync = qv.get("in_sync", False)
            lines.append(
                f"- **Qdrant Cross-Validation:** {'✅ In Sync' if in_sync else '❌ MISMATCH'} "
                f"(Qdrant: {qv.get('qdrant_points', '?')}, DB: {qv.get('db_chunk_count', '?')})"
            )
            lines.append("")

    # Layer 5: Retrieval
    ret = layers.get("retrieval")
    if ret:
        avg = ret.get("avg_scores", {})
        lines.extend([
            "## Layer 5: Retrieval Quality (LLM-as-Judge)",
            f"- **Questions:** {ret.get('num_questions', '?')}",
            f"- **Total Time:** {ret.get('total_time_sec', '?'):.1f}s" if isinstance(ret.get('total_time_sec'), (int, float)) else f"- **Total Time:** {ret.get('total_time_sec', '?')}",
            f"- **Faithfulness:** {avg.get('faithfulness', '?'):.2f}",
            f"- **Answer Relevancy:** {avg.get('answer_relevancy', '?'):.2f}",
            f"- **Context Precision:** {avg.get('context_precision', '?'):.2f}",
            f"- **Context Recall:** {avg.get('context_recall', '?'):.2f}",
            f"- **Noise Sensitivity:** {avg.get('noise_sensitivity', '?'):.2f}",
            "",
        ])

    lines.append("---")
    return "\n".join(lines)


def compare_baseline(result: Dict[str, Any], baseline_path: str | None = None) -> Dict[str, Any]:
    """Compare an evaluation result against a baseline (previous report).

    Args:
        result: Current evaluation result.
        baseline_path: Path to baseline JSON file. If None, looks for latest.

    Returns:
        Dict with: same_structure as result but with "delta" values, plus "regression" list.
    """
    if baseline_path is None:
        coll = result.get("collection_name", "?")
        latest = _latest_report(coll)
        if not latest:
            return {"status": "no_baseline", "message": "No previous report found"}
        baseline_path = str(latest)

    try:
        with open(baseline_path) as f:
            baseline = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"status": "error", "message": f"Cannot read baseline: {baseline_path}"}

    current_layers = result.get("layers", {})
    baseline_layers = baseline.get("layers", {})

    diffs = {}
    regressions = []

    for layer_name in current_layers:
        current_scores = current_layers.get(layer_name, {})
        baseline_scores = baseline_layers.get(layer_name, {})

        if isinstance(current_scores, dict):
            layer_diff = {}
            for key in current_scores:
                cv = current_scores[key]
                bv = baseline_scores.get(key)
                if isinstance(cv, (int, float)) and isinstance(bv, (int, float)):
                    delta = round(cv - bv, 4)
                    layer_diff[key] = {
                        "current": cv,
                        "baseline": bv,
                        "delta": delta,
                    }
                    # Flag regressions (negative delta for metrics where higher is better)
                    if key in ("success_rate", "faithfulness", "context_precision", "context_recall", "answer_relevancy", "dimension_utilization"):
                        if delta < -0.05:
                            regressions.append(f"{layer_name}.{key}: {bv:.4f} -> {cv:.4f} ({delta:+.4f})")
                    elif key in ("error_rate", "zero_vector_rate", "empty_chunks", "empty_extraction_rate"):
                        if delta > 0.05:
                            regressions.append(f"{layer_name}.{key}: {bv:.4f} -> {cv:.4f} (worsened by {delta:+.4f})")
                else:
                    layer_diff[key] = {"current": cv, "baseline": bv, "delta": None}
            diffs[layer_name] = layer_diff

    return {
        "status": "compared",
        "baseline_path": baseline_path,
        "regression_count": len(regressions),
        "regressions": regressions,
        "diffs": diffs,
    }
