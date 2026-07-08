"""NLP/NER entity extraction and Neo4j graph storage strategies."""

import os
import logging
from typing import List, Dict, Any, Optional

try:
    import spacy
except ImportError:
    spacy = None  # type: ignore[assignment]

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None  # type: ignore[assignment]

from core.base_strategies import BaseGraphIndexingStrategy, GraphEntity, GraphRelation, Chunk, Document
from core.registry import StrategyRegistry

logger = logging.getLogger(__name__)


class NEREntityExtractor:
    """Named Entity Recognition extractor using spaCy."""
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        self.model_name = model_name
        self.nlp = None
        self._load_model()
    
    def _load_model(self):
        """Load the spaCy model."""
        if spacy is None:
            logger.warning("spaCy not installed — NER strategies will be unavailable")
            return
        try:
            self.nlp = spacy.load(self.model_name)
            logger.info(f"Loaded spaCy model: {self.model_name}")
        except OSError:
            logger.warning(f"spaCy model '{self.model_name}' not found. Trying to download...")
            try:
                spacy.cli.download(self.model_name)
                self.nlp = spacy.load(self.model_name)
                logger.info(f"Downloaded and loaded spaCy model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to load/download spaCy model {self.model_name}: {e}")
                # Fallback to blank English model
                self.nlp = spacy.blank("en")
                logger.warning("Using blank English model - NER will not be available")
    
    def extract_entities_and_relations(self, text: str) -> tuple[List[Dict], List[Dict]]:
        """Extract entities and relations from text.
        
        Returns:
            Tuple of (entities, relations) where each is a list of dicts.
        """
        if not self.nlp or not text.strip():
            return [], []
        
        doc = self.nlp(text)
        
        # Extract entities
        entities = []
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "description": (spacy.explain(ent.label_) if spacy else None) or ent.label_,
            })
        
        # Extract relations (simplified - in production you'd use dependency parsing or RE models)
        relations = []
        # For now, we'll create simple co-occurrence relations within sentences
        for sent in doc.sents:
            sent_ents = [ent for ent in ents if ent.start >= sent.start_char and ent.end <= sent.end_char]
            # Create relations between entities in the same sentence
            for i, ent1 in enumerate(sent_ents):
                for ent2 in sent_ents[i+1:]:
                    relations.append({
                        "source_text": ent1.text,
                        "source_label": ent1.label_,
                        "target_text": ent2.text,
                        "target_label": ent2.label_,
                        "relation_type": "CO_OCCURS_WITH",
                        "sentence": sent.text
                    })
        
        return entities, relations


class Neo4jGraphIndexingConfig:
    """Configuration for Neo4j graph database."""
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        self.entity_label = "Entity"
        self.relation_label = "RELATION"


class Neo4jGraphIndexingStrategy(BaseGraphIndexingStrategy):
    """Store entities and relationships in Neo4j graph database."""
    
    def __init__(self, config: Optional[Neo4jGraphIndexingConfig] = None):
        self.config = config or Neo4jGraphIndexingConfig()
        self.driver = None
        self.ner_extractor = NEREntityExtractor()
        self._initialize_driver()
    
    def _initialize_driver(self):
        """Initialize Neo4j driver."""
        if GraphDatabase is None:
            logger.warning("neo4j driver not installed — graph indexing will be unavailable")
            return
        try:
            self.driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
                database=self.config.database
            )
            # Verify connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info(f"Connected to Neo4j at {self.config.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    def close(self):
        """Close the Neo4j driver."""
        if self.driver:
            self.driver.close()
    
    def _ensure_constraints_and_indexes(self):
        """Create necessary constraints and indexes for performance."""
        with self.driver.session() as session:
            # Create constraint for entity uniqueness
            try:
                session.run(f"""
                    CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
                    FOR (e:{self.config.entity_label}) REQUIRE e.id IS UNIQUE
                """)
            except Exception as e:
                # Ignore if constraint already exists
                pass
            
            # Create indexes for common properties
            try:
                session.run(f"""
                    CREATE INDEX entity_name IF NOT EXISTS
                    FOR (e:{self.config.entity_label}) ON (e.name)
                """)
            except Exception as e:
                pass
            
            try:
                session.run(f"""
                    CREATE INDEX entity_type IF NOT EXISTS
                    FOR (e:{self.config.entity_label}) ON (e.label)
                """)
            except Exception as e:
                pass
    
    def _create_entity_node(self, entity: GraphEntity) -> None:
        """Create or merge an entity node in Neo4j."""
        with self.driver.session() as session:
            query = f"""
            MERGE (e:{self.config.entity_label} {{id: $id}})
            SET e.label = $label,
                e.name = $name,
                e.collection_name = $collection_name,
                e.connector_id = $connector_id,
                e.external_id = $external_id,
                e += $properties
            """
            params = {
                "id": entity.id,
                "label": entity.label,
                "name": entity.name,
                "collection_name": entity.properties.get("collection_name", ""),
                "connector_id": entity.properties.get("connector_id", ""),
                "external_id": entity.properties.get("external_id", ""),
                "properties": entity.properties,
            }
            session.run(query, parameters=params)
    
    def _create_relationship(self, relation: GraphRelation) -> None:
        """Create a relationship between entities in Neo4j."""
        with self.driver.session() as session:
            query = f"""
            MATCH (a:{self.config.entity_label} {{id: $source_id}})
            MATCH (b:{self.config.entity_label} {{id: $target_id}})
            MERGE (a)-[r:{self.config.relation_label} {{id: $id, type: $label}}]->(b)
            SET r += $properties
            """
            params = {
                "source_id": relation.source_id,
                "target_id": relation.target_id,
                "id": relation.id,
                "label": relation.label,
                "properties": relation.properties
            }
            session.run(query, parameters=params)
    
    def index_graph(self, entities: List[GraphEntity], relations: List[GraphRelation], **kwargs) -> None:
        """Index entities and relationships in Neo4j.
        
        If entities and relations are not provided, extract them from chunks/documents.
        """
        # If no explicit entities/relations provided, extract from documents/chunks
        if not entities and not relations:
            # Get documents and chunks from kwargs
            documents = kwargs.get("documents", [])
            chunks = kwargs.get("chunks", [])
            
            all_text = ""
            for doc in documents:
                all_text += " " + doc.content
            for chunk in chunks:
                all_text += " " + chunk.content
            
            if not all_text.strip():
                logger.warning("No text content found for entity extraction")
                return
            
            # Extract entities and relations
            raw_entities, raw_relations = self.ner_extractor.extract_entities_and_relations(all_text)
            
            # Convert to GraphEntity and GraphRelation objects
            entities = []
            for i, ent in enumerate(raw_entities):
                entities.append(GraphEntity(
                    id=f"ent_{i}_{hash(ent['text'])}",
                    label=ent["label"],
                    name=ent["text"],
                    properties={
                        "description": ent.get("description", ""),
                        "start_char": ent["start"],
                        "end_char": ent["end"],
                        "source_text": "extracted_from_documents"
                    }
                ))
            
            relations = []
            for i, rel in enumerate(raw_relations):
                # For simplicity, we'll create placeholder entity IDs
                # In a real implementation, you'd map text to entity IDs
                relations.append(GraphRelation(
                    id=f"rel_{i}",
                    source_id=f"source_{i}",  # Would need proper mapping
                    target_id=f"target_{i}",  # Would need proper mapping
                    label=rel["relation_type"],
                    properties={
                        "sentence": rel.get("sentence", ""),
                        "source_text": rel["source_text"],
                        "target_text": rel["target_text"]
                    }
                ))
        
        if not entities and not relations:
            logger.warning("No entities or relations to index")
            return
        
        try:
            # Ensure constraints and indexes exist
            self._ensure_constraints_and_indexes()
            
            # Create entity nodes
            for entity in entities:
                self._create_entity_node(entity)
            
            # Create relationships
            for relation in relations:
                self._create_relationship(relation)
            
            logger.info(f"Indexed {len(entities)} entities and {len(relations)} relations in Neo4j")
            
        except Exception as e:
            logger.error(f"Failed to index graph data in Neo4j: {e}")
            raise


# ───────────────────────────────────────────────────────────────
# New multi-index strategies — auto-import to ensure registration
# ───────────────────────────────────────────────────────────────
from . import qdrant_indexing       # noqa: F401 — registers qdrant_indexing
from . import qdrant_sparse_indexing  # noqa: F401 — registers qdrant_sparse_indexing
from . import metadata_indexing       # noqa: F401 — registers metadata_indexing
from . import memory_indexing         # noqa: F401 — registers memory_indexing

# Register the graph strategies
@StrategyRegistry.register("graph_indexing", "neo4j")
class Neo4jGraphIndexingAlias(Neo4jGraphIndexingStrategy):
    pass

@StrategyRegistry.register("graph_indexing", "ner_neo4j")
class NERNeo4jGraphIndexingAlias(Neo4jGraphIndexingStrategy):
    pass

# Register with indexing stage as well
@StrategyRegistry.register("indexing", "neo4j_graph")
class Neo4jGraphIndexingForIndexing(Neo4jGraphIndexingStrategy):
    pass

@StrategyRegistry.register("indexing", "ner_neo4j")
class NERNeo4jGraphIndexingForIndexing(Neo4jGraphIndexingStrategy):
    pass