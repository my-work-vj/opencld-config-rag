"""Memory indexing strategy — persists session context to Redis for Memory-Augmented RAG."""

import os
import json
import logging
from typing import Optional, Any

from core.base_strategies import BaseMemoryIndexingStrategy
from core.registry import StrategyRegistry

logger = logging.getLogger(__name__)


class RedisClient:
    """Singleton Redis client for memory store."""
    _instance: Optional["RedisClient"] = None
    _client = None

    def __init__(self):
        self._connect()

    def _connect(self):
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        try:
            import redis
            kwargs = {"host": redis_host, "port": redis_port, "decode_responses": True}
            if redis_password:
                kwargs["password"] = redis_password
            self._client = redis.Redis(**kwargs)
            self._client.ping()
            logger.info(f"RedisClient: connected to {redis_host}:{redis_port}")
        except Exception as e:
            logger.warning(f"RedisClient: cannot connect to Redis — {e}")
            self._client = None

    @classmethod
    def get(cls) -> Optional[Any]:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance._client

    @classmethod
    def close(cls):
        if cls._instance and cls._instance._client:
            try:
                cls._instance._client.close()
            except Exception:
                pass
            cls._instance = None


@StrategyRegistry.register("indexing", "memory_indexing")
class MemoryIndexing(BaseMemoryIndexingStrategy):
    """Store session-level conversational context in Redis for memory-augmented RAG strategies."""

    def __init__(self, **kwargs):
        self.redis = RedisClient.get()

    def _session_key(self, session_id: str, collection_name: str) -> str:
        return f"rag:memory:{collection_name}:{session_id}"

    def index_memory(self, session_id: str, context: dict[str, Any], **kwargs) -> None:
        """Persist session context to Redis with TTL."""
        if self.redis is None:
            logger.warning("MemoryIndexing: Redis unavailable — skipping")
            return

        collection_name = kwargs.get("collection_name", "rag_documents")
        ttl = int(kwargs.get("ttl_seconds", 86400))  # default 24h

        key = self._session_key(session_id, collection_name)
        try:
            existing = self.redis.get(key)
            if existing:
                data = json.loads(existing)
            else:
                data = {}

            # Merge new context into existing
            for k, v in context.items():
                if isinstance(v, list):
                    existing_list = data.get(k, [])
                    existing_list.extend(v)
                    data[k] = existing_list
                elif isinstance(v, dict):
                    existing_dict = data.get(k, {})
                    existing_dict.update(v)
                    data[k] = existing_dict
                else:
                    data[k] = v

            self.redis.setex(key, ttl, json.dumps(data))
            logger.info(
                f"MemoryIndexing: saved session '{session_id}' "
                f"(collection={collection_name}, ttl={ttl}s)"
            )
        except Exception as e:
            logger.error(f"MemoryIndexing: Redis error — {e}")

    def index_document_catalog(
        self,
        documents: list,
        chunks: list,
        **kwargs,
    ) -> None:
        """Persist per-document chunk catalog for memory-augmented retrieval."""
        if self.redis is None:
            logger.warning("MemoryIndexing: Redis unavailable — skipping document catalog")
            return

        collection_name = kwargs.get("collection_name", "rag_documents")
        connector_id = kwargs.get("connector_id", "")
        external_id = kwargs.get("external_id", "")
        if not connector_id or not external_id:
            return

        ttl = int(kwargs.get("ttl_seconds", 86400 * 7))
        key = f"rag:doc:{collection_name}:{connector_id}:{external_id}"
        previews = [
            {
                "chunk_id": c.id,
                "chunk_index": c.chunk_index,
                "preview": (c.content or "")[:300],
            }
            for c in chunks[:50]
        ]
        payload = {
            "collection_name": collection_name,
            "connector_id": connector_id,
            "external_id": external_id,
            "filename": kwargs.get("filename") or (documents[0].filename if documents else ""),
            "content_hash": kwargs.get("content_hash", ""),
            "chunk_count": len(chunks),
            "chunks": previews,
        }
        try:
            self.redis.setex(key, ttl, json.dumps(payload))
            logger.info(
                "MemoryIndexing: cataloged document %s/%s (%d chunks)",
                connector_id,
                external_id,
                len(chunks),
            )
        except Exception as e:
            logger.error(f"MemoryIndexing: document catalog error — {e}")

    def get_session(self, session_id: str, collection_name: str = "rag_documents") -> Optional[dict]:
        """Retrieve session context from Redis."""
        if self.redis is None:
            return None
        key = self._session_key(session_id, collection_name)
        try:
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"MemoryIndexing: Redis read error — {e}")
        return None
