"""IngestionPipeline orchestrator — ingestion through multi-index knowledge store indexing."""

import time
import logging
from typing import Any, Dict, List, Optional

from .registry import StrategyRegistry
from .base_strategies import (
    Document,
    Chunk,
    EmbeddingVector,
    SparseVector,
    GraphEntity,
    GraphRelation,
    PipelineContext,
)

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates ingestion → chunking → embedding → multi-index storage.
    
    This is the main ingestion pipeline that supports indexing to multiple stores
    simultaneously:
    - Dense vectors (Qdrant)
    - Sparse vectors (Qdrant sparse / BM25)
    - Graph entities/relations (Neo4j)
    - Document/chunk metadata (PostgreSQL)
    - Session memory (Redis)
    """

    def __init__(self, pipeline_config: dict[str, Any]):
        self.name = pipeline_config.get("pipeline", {}).get("name", "unnamed")
        self.config = pipeline_config.get("pipeline", {})
        self.stages_config = self.config.get("stages", {})

    @staticmethod
    def _merge_stage_config(base: dict, overrides: dict) -> dict:
        """Merge base configuration with overrides."""
        merged = dict(base)
        if overrides.get("strategy"):
            merged["strategy"] = overrides["strategy"]
        merged_config = dict(base.get("config", {}))
        merged_config.update(overrides.get("config", {}))
        merged["config"] = merged_config
        return merged

    @staticmethod
    def _load_strategy(stage_name: str, strategy_config: dict) -> tuple[Any, dict]:
        """Load a strategy instance from configuration."""
        strategy_name = strategy_config.get("strategy")
        strategy_kwargs = strategy_config.get("config", {})
        strategy = StrategyRegistry.get(stage_name, strategy_name)
        return strategy, strategy_kwargs

    def run_ingestion(self, source: Any, **overrides) -> list[Document]:
        """Run the ingestion stage."""
        cfg = self._merge_stage_config(
            self.stages_config.get("ingestion", {}), overrides
        )
        strategy, kwargs = self._load_strategy("ingestion", cfg)
        logger.info(f"[{self.name}] Ingestion: {type(strategy).__name__}")
        return strategy.ingest(source, **kwargs)

    def run_chunking(self, documents: list[Document], **overrides) -> list[Chunk]:
        """Run the chunking stage."""
        cfg = self._merge_stage_config(
            self.stages_config.get("chunking", {}), overrides
        )
        strategy, kwargs = self._load_strategy("chunking", cfg)
        logger.info(f"[{self.name}] Chunking: {type(strategy).__name__}")
        return strategy.chunk(documents, **kwargs)

    def run_embedding(self, chunks: list[Chunk], **overrides) -> list[EmbeddingVector]:
        """Run the embedding stage."""
        cfg = self._merge_stage_config(
            self.stages_config.get("embedding", {}), overrides
        )
        strategy, kwargs = self._load_strategy("embedding", cfg)
        logger.info(f"[{self.name}] Embedding: {type(strategy).__name__}")
        return strategy.embed(chunks, **kwargs)

    def run_sparse_embedding(self, chunks: list[Chunk], **overrides) -> list[SparseVector]:
        """Run the sparse embedding stage (optional)."""
        # Check if sparse embedding is configured
        sparse_config = self.stages_config.get("sparse_embedding")
        if not sparse_config:
            return []
        
        cfg = self._merge_stage_config(sparse_config, overrides)
        strategy, kwargs = self._load_strategy("sparse_embedding", cfg)
        logger.info(f"[{self.name}] Sparse Embedding: {type(strategy).__name__}")
        return strategy.embed_sparse(chunks, **kwargs.get("config", {}))

    def run_indexing(self, 
                    embeddings: list[EmbeddingVector],
                    sparse_vectors: list[SparseVector] = None,
                    graph_entities: list[GraphEntity] = None,
                    graph_relations: list[GraphRelation] = None,
                    documents: list[Document] = None,
                    chunks: list[Chunk] = None,
                    session_id: str = None,
                    context: dict = None,
                    content_hash: str | None = None,
                    **overrides) -> None:
        """Run all configured indexing stages."""
        if sparse_vectors is None:
            sparse_vectors = []
        if graph_entities is None:
            graph_entities = []
        if graph_relations is None:
            graph_relations = []
        
        # Get indexing configuration
        indexing_configs = self.stages_config.get("indexing", {})
        if not isinstance(indexing_configs, dict):
            indexing_configs = {"default": indexing_configs} if indexing_configs else {}

        # Backward compat: single-index format ({"strategy": "...", "config": {...}})
        # → wrap in multi-index dict
        if "strategy" in indexing_configs:
            indexing_configs = {"default": dict(indexing_configs)}
        
        # Run each configured indexer
        for index_name, index_config in indexing_configs.items():
            if not index_config:
                continue
            
            cfg = self._merge_stage_config(index_config, overrides)
            strategy_name = cfg.get("strategy")
            strategy_kwargs = cfg.get("config", {})
            
            try:
                strategy = StrategyRegistry.get("indexing", strategy_name)
                
                # Call the appropriate indexing method based on strategy type
                if hasattr(strategy, 'index_sparse') and sparse_vectors and 'sparse' in strategy_name.lower():
                    logger.info(f"[{self.name}] {index_name} (Sparse): {type(strategy).__name__}")
                    strategy.index_sparse(sparse_vectors, **strategy_kwargs)
                elif hasattr(strategy, 'index_graph') and (graph_entities or graph_relations) and 'graph' in strategy_name.lower():
                    logger.info(f"[{self.name}] {index_name} (Graph): {type(strategy).__name__}")
                    graph_kwargs = dict(strategy_kwargs)
                    if documents:
                        graph_kwargs["documents"] = documents
                    if chunks:
                        graph_kwargs["chunks"] = chunks
                    strategy.index_graph(graph_entities, graph_relations, **graph_kwargs)
                elif hasattr(strategy, 'index_metadata') and (documents or chunks) and 'metadata' in strategy_name.lower():
                    logger.info(f"[{self.name}] {index_name} (Metadata): {type(strategy).__name__}")
                    meta_kwargs = dict(strategy_kwargs)
                    if content_hash:
                        meta_kwargs["content_hash"] = content_hash
                    strategy.index_metadata(documents, chunks, **meta_kwargs)
                elif hasattr(strategy, 'index_memory') and 'memory' in strategy_name.lower():
                    logger.info(f"[{self.name}] {index_name} (Memory): {type(strategy).__name__}")
                    mem_kwargs = dict(strategy_kwargs)
                    if content_hash:
                        mem_kwargs["content_hash"] = content_hash
                    if context:
                        mem_kwargs.update({
                            k: context[k]
                            for k in ("connector_id", "external_id", "filename")
                            if k in context
                        })
                    if documents or chunks:
                        catalog_kwargs = dict(mem_kwargs)
                        strategy.index_document_catalog(
                            documents or [],
                            chunks or [],
                            **catalog_kwargs,
                        )
                    if session_id:
                        strategy.index_memory(session_id, context or {}, **mem_kwargs)
                elif hasattr(strategy, 'index'):
                    logger.info(f"[{self.name}] {index_name} (Dense): {type(strategy).__name__}")
                    strategy.index(embeddings, **strategy_kwargs)
                else:
                    logger.warning(f"[{self.name}] Unknown indexing strategy type: {strategy_name}")
                    
            except Exception as e:
                logger.error(f"Failed to run indexer {index_name} ({strategy_name}): {e}")
                # Continue with other indexers rather than failing completely

    def _graph_index_enabled(self) -> bool:
        indexing = self.stages_config.get("indexing", {})
        if not isinstance(indexing, dict):
            return False
        if "strategy" in indexing:
            name = indexing.get("strategy", "")
            return "graph" in name.lower() or "neo4j" in name.lower()
        return any(
            isinstance(cfg, dict)
            and (
                "graph" in k.lower()
                or "neo4j" in (cfg.get("strategy") or "").lower()
            )
            for k, cfg in indexing.items()
        )

    def _memory_index_enabled(self) -> bool:
        indexing = self.stages_config.get("indexing", {})
        if not isinstance(indexing, dict):
            return False
        if "strategy" in indexing:
            return "memory" in (indexing.get("strategy") or "").lower()
        return any(
            "memory" in k.lower()
            for k in indexing
        )

    def run(
        self,
        source: Any,
        ingestion_overrides: dict | None = None,
        chunking_overrides: dict | None = None,
        embedding_overrides: dict | None = None,
        sparse_embedding_overrides: dict | None = None,
        indexing_overrides: dict | None = None,
        source_metadata: dict | None = None,
        content_hash: str | None = None,
    ) -> PipelineContext:
        """Run the full ingestion pipeline with multi-index support."""
        ctx = PipelineContext(pipeline_name=self.name, config=self.config)
        timings = {}

        # 1. Ingestion
        t0 = time.time()
        ctx.documents = self.run_ingestion(source, **(ingestion_overrides or {}))
        timings["ingestion"] = time.time() - t0
        logger.info(f"Ingested {len(ctx.documents)} documents")

        if source_metadata:
            for doc in ctx.documents:
                doc.metadata.update(source_metadata)
                if source_metadata.get("filename"):
                    doc.filename = source_metadata["filename"]
                if content_hash:
                    doc.metadata["content_hash"] = content_hash

        # 2. Chunking
        t0 = time.time()
        ctx.chunks = self.run_chunking(ctx.documents, **(chunking_overrides or {}))
        timings["chunking"] = time.time() - t0
        logger.info(f"Created {len(ctx.chunks)} chunks")

        # 3. Embedding (dense)
        t0 = time.time()
        ctx.embeddings = self.run_embedding(ctx.chunks, **(embedding_overrides or {}))
        timings["embedding"] = time.time() - t0
        logger.info(f"Generated {len(ctx.embeddings)} dense embeddings")

        # 4. Sparse Embedding (optional)
        t0 = time.time()
        ctx.sparse_vectors = self.run_sparse_embedding(ctx.chunks, **(sparse_embedding_overrides or {}))
        timings["sparse_embedding"] = time.time() - t0
        if ctx.sparse_vectors:
            logger.info(f"Generated {len(ctx.sparse_vectors)} sparse vectors")

        # 5. Graph Entity/Relation Extraction (when graph index enabled)
        t0 = time.time()
        if self._graph_index_enabled():
            ctx.graph_entities, ctx.graph_relations = self._extract_entities_and_relations(
                ctx.chunks,
                source_metadata=source_metadata or {},
            )
            if ctx.graph_entities or ctx.graph_relations:
                logger.info(
                    f"Extracted {len(ctx.graph_entities)} entities and "
                    f"{len(ctx.graph_relations)} relations"
                )
        else:
            ctx.graph_entities, ctx.graph_relations = [], []
        timings["graph_extraction"] = time.time() - t0

        # 6. Multi-Index Storage
        t0 = time.time()
        memory_session = None
        if source_metadata and self._memory_index_enabled():
            memory_session = (
                f"{source_metadata.get('connector_id', '')}:"
                f"{source_metadata.get('external_id', '')}"
            )
        self.run_indexing(
            embeddings=ctx.embeddings,
            sparse_vectors=ctx.sparse_vectors,
            graph_entities=ctx.graph_entities,
            graph_relations=ctx.graph_relations,
            documents=ctx.documents,
            chunks=ctx.chunks,
            session_id=memory_session,
            context={
                "documents": ctx.documents,
                "chunks": ctx.chunks,
                **(source_metadata or {}),
            },
            content_hash=content_hash,
            **(indexing_overrides or {}),
        )
        timings["indexing"] = time.time() - t0
        logger.info("Multi-index storage complete")

        # 7. Store timings and collection info
        ctx.state["timings"] = timings
        ctx.state["collection_name"] = (
            self.stages_config.get("indexing", {})
            .get("default", {})
            .get("config", {})
            .get("collection_name", "rag_documents")
        )

        return ctx

    def _extract_entities_and_relations(
        self,
        chunks: list[Chunk],
        *,
        source_metadata: dict | None = None,
    ) -> tuple[list[GraphEntity], list[GraphRelation]]:
        """Extract entities and relations from chunks for knowledge graph.
        
        This is a simplified implementation. In production, you would use:
        - spaCy with NER models
        - Hugging Face transformers for NER
        - LLMs for entity extraction
        - Rule-based extractors for specific domains
        """
        entities = []
        relations = []
        
        # Simple entity extraction - look for capitalized phrases
        import re
        
        entity_id_counter = 0
        relation_id_counter = 0
        
        # Track entity mentions to avoid duplicates
        entity_map = {}  # normalized_name -> entity_id
        
        source_metadata = source_metadata or {}
        collection_name = source_metadata.get("qdrant_collection", "")
        connector_id = source_metadata.get("connector_id", "")
        external_id = source_metadata.get("external_id", "")

        for chunk in chunks:
            text = chunk.content
            
            # Find potential entities (simplified: capitalized words/phrases)
            # This is very basic - replace with proper NER in production
            potential_entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
            
            # Also look for quoted terms
            quoted_terms = re.findall(r'"([^"]*)"', text)
            potential_entities.extend(quoted_terms)
            
            # Also look for ALL CAPS words (acronyms)
            acronyms = re.findall(r'\b[A-Z]{2,}\b', text)
            potential_entities.extend(acronyms)
            
            # Process each potential entity
            for entity_name in potential_entities:
                if len(entity_name.strip()) < 2:  # Skip very short
                    continue
                
                normalized_name = entity_name.strip().lower()
                
                if normalized_name not in entity_map:
                    entity_id = f"ent_{entity_id_counter}"
                    entity_id_counter += 1
                    
                    # Determine entity type (simplified)
                    entity_type = "ENTITY"
                    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', entity_name):
                        entity_type = "PERSON_OR_ORG"
                    elif re.match(r'^[A-Z]{2,}$', entity_name):
                        entity_type = "ACRONYM"
                    elif '"' in entity_name or "'" in entity_name:
                        entity_type = "QUOTED_TERM"
                    
                    entity = GraphEntity(
                        id=entity_id,
                        label=entity_type,
                        name=entity_name,
                        properties={
                            "source_chunk": chunk.id,
                            "source_document": chunk.document_id,
                            "collection_name": collection_name,
                            "connector_id": connector_id,
                            "external_id": external_id,
                            "mention_count": 1,
                            "first_seen": chunk.content[:100],
                        },
                    )
                    entities.append(entity)
                    entity_map[normalized_name] = entity_id
                else:
                    # Entity already exists, increment mention count
                    existing_entity_id = entity_map[normalized_name]
                    # In a real implementation, we'd update the existing entity
                    # For now, we'll note that this entity was mentioned again
                    
                    # Create a co-mention relationship
                    relation_id = f"rel_{relation_id_counter}"
                    relation_id_counter += 1
                    
                    # Find another entity in the same chunk to relate to
                    # This is very simplistic - real NER would do proper relation extraction
                    other_entities_in_chunk = [
                        e for e in entities 
                        if e.id != existing_entity_id and 
                        any(ent.name in chunk.content for ent in [e])
                    ]
                    
                    if other_entities_in_chunk:
                        # Create a relation to the first other entity found
                        other_entity = other_entities_in_chunk[0]
                        relation = GraphRelation(
                            id=relation_id,
                            source_id=existing_entity_id,
                            target_id=other_entity.id,
                            label="CO_MENTIONED",
                            properties={
                                "source_chunk": chunk.id,
                                "context": chunk.content[:200]
                            }
                        )
                        relations.append(relation)
        
        return entities, relations