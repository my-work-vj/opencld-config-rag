"""Multi-index CRUD — provision and delete across Qdrant, PostgreSQL, Neo4j, Redis."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

from rag_shared.index_config import normalize_index_config

logger = logging.getLogger(__name__)


def _qdrant_client() -> QdrantClient:
    return QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )


def _connector_file_filter(connector_id: str, external_id: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(key="connector_id", match=MatchValue(value=connector_id)),
            FieldCondition(key="external_id", match=MatchValue(value=external_id)),
        ]
    )


def ensure_qdrant_collection(
    collection_name: str,
    vector_size: int = 2048,
    distance: str = "Cosine",
    *,
    enable_sparse: bool = False,
) -> None:
    """Create Qdrant collection with dense vectors and optional sparse vectors."""
    client = _qdrant_client()
    distance_map = {
        "Cosine": Distance.COSINE,
        "Dot": Distance.DOT,
        "Euclid": Distance.EUCLID,
    }
    dist = distance_map.get(distance, Distance.COSINE)
    existing = {c.name for c in client.get_collections().collections}
    if collection_name in existing:
        if enable_sparse:
            info = client.get_collection(collection_name)
            if not info.config.params.sparse_vectors:
                logger.warning(
                    "Collection '%s' exists without sparse vectors — recreate to enable sparse",
                    collection_name,
                )
        return

    kwargs: dict[str, Any] = {
        "collection_name": collection_name,
        "vectors_config": VectorParams(size=vector_size, distance=dist),
    }
    if enable_sparse:
        kwargs["sparse_vectors_config"] = {
            "sparse": SparseVectorParams(index=SparseIndexParams()),
        }
    client.create_collection(**kwargs)
    logger.info(
        "Created Qdrant collection '%s' (size=%s, sparse=%s)",
        collection_name,
        vector_size,
        enable_sparse,
    )


def ensure_neo4j_constraints() -> None:
    try:
        from neo4j import GraphDatabase
    except ImportError:
        logger.warning("neo4j driver not installed — graph index provisioning skipped")
        return

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run(
                "CREATE INDEX entity_collection IF NOT EXISTS "
                "FOR (e:Entity) ON (e.collection_name)"
            )
            session.run(
                "CREATE INDEX entity_external IF NOT EXISTS "
                "FOR (e:Entity) ON (e.external_id)"
            )
        driver.close()
    except Exception as exc:
        logger.warning("Neo4j constraint setup failed: %s", exc)


def ensure_redis_available() -> bool:
    try:
        import redis

        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        client = redis.Redis(host=host, port=port, decode_responses=True)
        client.ping()
        return True
    except Exception as exc:
        logger.warning("Redis not available: %s", exc)
        return False


def ensure_collection_indexes(
    collection_name: str,
    vector_size: int,
    index_config: dict[str, Any] | None,
) -> dict[str, bool]:
    """Provision backing stores for enabled index types."""
    flags = normalize_index_config(index_config)
    status = {
        "vector": False,
        "sparse": False,
        "graph": False,
        "metadata": True,
        "memory": False,
    }

    if flags["vector"] or flags["sparse"]:
        try:
            ensure_qdrant_collection(
                collection_name,
                vector_size=vector_size,
                enable_sparse=flags["sparse"],
            )
            status["vector"] = flags["vector"]
            status["sparse"] = flags["sparse"]
        except Exception as exc:
            logger.error("Qdrant provisioning failed: %s", exc)

    if flags["graph"]:
        try:
            ensure_neo4j_constraints()
            status["graph"] = True
        except Exception as exc:
            logger.error("Neo4j provisioning failed: %s", exc)

    if flags["memory"]:
        status["memory"] = ensure_redis_available()

    return status


def delete_qdrant_vectors(
    qdrant_collection: str,
    connector_id: str,
    external_id: str,
) -> None:
    client = _qdrant_client()
    try:
        client.delete(
            collection_name=qdrant_collection,
            points_selector=FilterSelector(
                filter=_connector_file_filter(connector_id, external_id),
            ),
        )
    except Exception as exc:
        logger.warning(
            "Qdrant delete failed for %s/%s in %s: %s",
            connector_id,
            external_id,
            qdrant_collection,
            exc,
        )


def delete_metadata_records(
    collection_name: str,
    connector_id: str,
    external_id: str,
) -> None:
    try:
        from core.db import SessionLocal
        from core.models import ChunkRecord, DocumentRecord
    except ImportError:
        logger.warning("Metadata delete skipped — core.models unavailable")
        return

    db = SessionLocal()
    try:
        docs = (
            db.query(DocumentRecord)
            .filter(DocumentRecord.collection_name == collection_name)
            .all()
        )
        for doc in docs:
            meta = doc.metadata_json or {}
            if (
                meta.get("connector_id") == connector_id
                and meta.get("external_id") == external_id
            ):
                db.query(ChunkRecord).filter(
                    ChunkRecord.document_id == doc.id,
                ).delete(synchronize_session=False)
                db.delete(doc)

        chunks = db.query(ChunkRecord).all()
        for chunk in chunks:
            meta = chunk.metadata_json or {}
            if (
                meta.get("connector_id") == connector_id
                and meta.get("external_id") == external_id
            ):
                db.delete(chunk)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Metadata delete failed: %s", exc)
    finally:
        db.close()


def delete_neo4j_document(
    collection_name: str,
    connector_id: str,
    external_id: str,
) -> None:
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run(
                """
                MATCH (e:Entity)
                WHERE e.collection_name = $collection
                  AND e.connector_id = $connector_id
                  AND e.external_id = $external_id
                DETACH DELETE e
                """,
                collection=collection_name,
                connector_id=connector_id,
                external_id=external_id,
            )
        driver.close()
    except Exception as exc:
        logger.warning("Neo4j delete failed: %s", exc)


def delete_memory_document(
    collection_name: str,
    connector_id: str,
    external_id: str,
) -> None:
    try:
        import redis
    except ImportError:
        return

    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    try:
        client = redis.Redis(host=host, port=port, decode_responses=True)
        key = f"rag:doc:{collection_name}:{connector_id}:{external_id}"
        client.delete(key)
        pattern = f"rag:memory:{collection_name}:{connector_id}:{external_id}*"
        for match in client.scan_iter(match=pattern):
            client.delete(match)
    except Exception as exc:
        logger.warning("Redis delete failed: %s", exc)


def delete_document_from_all_indexes(
    qdrant_collection: str,
    collection_name: str,
    connector_id: str,
    external_id: str,
    index_config: dict[str, Any] | None = None,
) -> None:
    """Remove a connector file from every enabled index (incremental delete)."""
    flags = normalize_index_config(index_config)

    if flags["vector"] or flags["sparse"]:
        delete_qdrant_vectors(qdrant_collection, connector_id, external_id)

    if flags["metadata"]:
        delete_metadata_records(collection_name, connector_id, external_id)

    if flags["graph"]:
        delete_neo4j_document(collection_name, connector_id, external_id)

    if flags["memory"]:
        delete_memory_document(collection_name, connector_id, external_id)

    logger.info(
        "Deleted document indexes for %s/%s in collection %s (flags=%s)",
        connector_id,
        external_id,
        collection_name,
        flags,
    )


# Backward-compatible alias
delete_connector_file_vectors = delete_qdrant_vectors
