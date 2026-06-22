"""Threshold-based pass/fail checking for evaluation metrics.

Loads thresholds from thresholds.yaml and checks evaluation results.
"""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _default_thresholds_path() -> str:
    """Return path to thresholds.yaml in the evaluation directory."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "thresholds.yaml")


def load_thresholds(path: Optional[str] = None) -> Dict[str, Any]:
    """Load thresholds from YAML file."""
    path = path or _default_thresholds_path()
    p = Path(path)
    if not p.exists():
        return {}
    with open(p) as f:
        return yaml.safe_load(f) or {}


def check_thresholds(
    eval_result: Dict[str, Any],
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Check evaluation metrics against defined thresholds.

    Args:
        eval_result: The result dict from run_evaluation() (with 'layers' key).
        thresholds: Thresholds dict (loaded from YAML). If None, loads defaults.

    Returns:
        {
            "status": "pass" | "fail" | "no_thresholds",
            "results": {
                "<layer>": {
                    "<metric>": {
                        "value": float,
                        "threshold": {"min": ..., "max": ...},
                        "passed": bool,
                        "message": str,
                    },
                    ...
                },
                ...
            },
            "failures": [list of failed metric descriptions],
        }
    """
    thresholds = thresholds or load_thresholds()
    if not thresholds:
        return {"status": "no_thresholds", "results": {}, "failures": []}

    layers = eval_result.get("layers", {})
    results: Dict[str, Any] = {}
    failures: List[str] = []

    for layer_name, layer_thresholds in thresholds.items():
        layer_result = layers.get(layer_name, {})
        if not layer_result:
            continue

        layer_checks: Dict[str, Any] = {}
        for metric_name, bounds in layer_thresholds.items():
            if not bounds.get("enabled", True):
                continue

            value = layer_result.get(metric_name)
            if value is None:
                # Try nested paths like pipeline.total_documents
                for key in layer_result:
                    if isinstance(layer_result[key], dict) and metric_name in layer_result[key]:
                        value = layer_result[key][metric_name]
                        break

            if value is None:
                continue
            if not isinstance(value, (int, float)):
                continue

            min_val = bounds.get("min")
            max_val = bounds.get("max")
            passed = True
            messages = []

            if min_val is not None and value < min_val:
                passed = False
                messages.append(f"below minimum {min_val} (value={value})")
            if max_val is not None and value > max_val:
                passed = False
                messages.append(f"above maximum {max_val} (value={value})")

            msg = "; ".join(messages) if messages else "OK"
            if not passed:
                failures.append(f"{layer_name}.{metric_name}: {msg}")

            layer_checks[metric_name] = {
                "value": value,
                "threshold": {"min": min_val, "max": max_val},
                "passed": passed,
                "message": msg,
            }

        if layer_checks:
            results[layer_name] = layer_checks

    return {
        "status": "fail" if failures else "pass",
        "results": results,
        "failures": failures,
    }


def format_threshold_report(threshold_result: Dict[str, Any]) -> str:
    """Format threshold check results as a human-readable string."""
    if threshold_result["status"] == "no_thresholds":
        return "  No thresholds configured — skipping checks."

    lines = [f"  Threshold Check: {threshold_result['status'].upper()}"]
    if not threshold_result["failures"]:
        lines.append("  All metrics passed ✓")

    for layer_name, checks in threshold_result.get("results", {}).items():
        lines.append(f"  [{layer_name}]")
        for metric_name, check in checks.items():
            indicator = "✓" if check["passed"] else "✗"
            lines.append(f"    {indicator} {metric_name}: {check['value']}")
        lines.append("")

    if threshold_result["failures"]:
        lines.append("  Failures:")
        for f in threshold_result["failures"]:
            lines.append(f"    ✗ {f}")

    return "\n".join(lines)
