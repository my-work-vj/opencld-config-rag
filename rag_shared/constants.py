"""Stage ownership constants for the two-service split."""

INGESTION_STAGES = ("ingestion", "chunking", "embedding", "indexing")

QUERY_STAGES = ("knowledge_store", "retrieval", "reranking", "response")

ALL_STAGES = INGESTION_STAGES + QUERY_STAGES
