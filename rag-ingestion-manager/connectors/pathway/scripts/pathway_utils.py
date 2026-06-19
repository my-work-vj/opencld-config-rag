"""Helpers for Pathway pw.io.subscribe callbacks (0.31+)."""

from __future__ import annotations

from typing import Any


def _to_python(value: Any) -> Any:
    if hasattr(value, "as_dict") and not isinstance(value, (bytes, str, int, float, bool)):
        try:
            inner = value.as_dict()
        except Exception:
            return value
        if isinstance(inner, dict):
            return {k: _to_python(v) for k, v in inner.items()}
        return inner
    if isinstance(value, dict):
        return {k: _to_python(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_python(item) for item in value]
    return value


def subscribe_row_dict(row: Any) -> dict[str, Any]:
    """Convert a subscribe callback row (dict or pw.Json) to a plain Python dict."""
    if hasattr(row, "as_dict"):
        raw = row.as_dict()
    elif isinstance(row, dict):
        raw = row
    else:
        raise TypeError(f"Unexpected subscribe row type: {type(row)}")
    return {k: _to_python(v) for k, v in raw.items()}
