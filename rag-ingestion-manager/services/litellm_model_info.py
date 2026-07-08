"""Fetch and cache LiteLLM model metadata (including multimodal embedding models)."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300
_model_info_cache: dict[str, Any] | None = None
_model_info_fetched_at: float = 0.0
_embedding_dims_cache: dict[str, int] = {}


def _litellm_root() -> str:
    base = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1").rstrip("/")
    if base.endswith("/v1"):
        return base[:-3]
    return base


def _fetch_model_info_payload() -> dict[str, Any]:
    global _model_info_cache, _model_info_fetched_at

    now = time.time()
    if _model_info_cache is not None and (now - _model_info_fetched_at) < _CACHE_TTL_SECONDS:
        return _model_info_cache

    api_key = os.getenv("LITELLM_API_KEY", "sk-vj")
    headers = {"Authorization": f"Bearer {api_key}"}
    root = _litellm_root()
    endpoints = (
        f"{root}/v1/model_info",
        f"{root}/model/info",
    )

    last_error: Exception | None = None
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                payload = json.loads(response.read())
            _model_info_cache = payload
            _model_info_fetched_at = now
            logger.debug("Loaded LiteLLM model info from %s", url)
            return payload
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.debug("LiteLLM model info unavailable at %s: %s", url, exc)

    if _model_info_cache is not None:
        return _model_info_cache

    raise RuntimeError(f"Could not fetch LiteLLM model info: {last_error}")


def list_model_entries() -> list[dict[str, Any]]:
    payload = _fetch_model_info_payload()
    return list(payload.get("data") or [])


def get_model_entry(model_name: str) -> dict[str, Any] | None:
    for item in list_model_entries():
        if item.get("model_name") == model_name:
            return item
    return None


def _backend_model_name(entry: dict[str, Any]) -> str:
    litellm_params = entry.get("litellm_params") or {}
    return str(litellm_params.get("model") or entry.get("model_info", {}).get("key") or "")


def supports_multimodal_embedding(entry: dict[str, Any]) -> bool:
    model_info = entry.get("model_info") or {}
    if model_info.get("supports_embedding_image_input"):
        return True
    backend = _backend_model_name(entry).lower()
    if "embed-vl" in backend or "vision" in backend or "multimodal" in backend:
        return True
    return model_info.get("mode") == "embedding" and "vl" in backend


def probe_embedding_dimensions(model_name: str) -> int:
    if model_name in _embedding_dims_cache:
        return _embedding_dims_cache[model_name]

    from strategies.embedding import LiteLLMClient

    client = LiteLLMClient.get_client().client
    resp = client.embeddings.create(
        model=model_name,
        input=["dimension probe"],
        extra_body={"input_type": "passage", "encoding_format": "float"},
    )
    dims = len(resp.data[0].embedding)
    _embedding_dims_cache[model_name] = dims
    return dims


def get_embedding_model_info(model_name: str | None = None) -> dict[str, Any]:
    """Return resolved embedding model metadata for pipeline configuration."""
    resolved_name = model_name or os.getenv("EMBEDDING_MODEL", "nvidia-embed")
    entry = get_model_entry(resolved_name)

    if not entry:
        return {
            "model_name": resolved_name,
            "mode": "embedding",
            "supports_multimodal": resolved_name == "nvidia-embed",
            "output_dimensions": int(os.getenv("DEFAULT_VECTOR_SIZE", "2048")),
            "backend_model": resolved_name,
        }

    model_info = entry.get("model_info") or {}
    output_dimensions = model_info.get("output_vector_size")
    if not output_dimensions:
        try:
            output_dimensions = probe_embedding_dimensions(resolved_name)
        except Exception as exc:
            logger.warning("Could not probe embedding dimensions for %s: %s", resolved_name, exc)
            output_dimensions = int(os.getenv("DEFAULT_VECTOR_SIZE", "2048"))

    return {
        "model_name": resolved_name,
        "mode": model_info.get("mode", "embedding"),
        "supports_multimodal": supports_multimodal_embedding(entry),
        "output_dimensions": int(output_dimensions),
        "backend_model": _backend_model_name(entry),
        "provider": model_info.get("provider") or model_info.get("litellm_provider"),
        "raw": entry,
    }
