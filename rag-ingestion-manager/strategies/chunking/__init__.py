"""Multi-granularity chunking strategies for hierarchical retrieval."""

import re
import uuid
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from core.base_strategies import BaseChunkingStrategy, Document, Chunk
from core.registry import StrategyRegistry

logger = logging.getLogger(__name__)

@dataclass
class HierarchicalChunkingConfig:
    """Configuration for hierarchical chunking."""
    child_chunk_size: int = 128  # Small chunks for precise retrieval
    parent_chunk_size: int = 768  # Larger chunks for context
    summary_chunk_size: int = 150  # Very small for summarization
    child_overlap: int = 16
    parent_overlap: int = 64
    summary_overlap: int = 12
    separators: List[str] = field(default_factory=lambda: ["\n\n", "\n", ". ", " ", ""])
    create_summary_level: bool = True  # Whether to create summary level
    summary_method: str = "extractive"  # extractive, abstractive (placeholder)

@dataclass
class ChunkHierarchy:
    """Represents the hierarchical relationship between chunks."""
    child_chunks: List[str] = field(default_factory=list)  # List of child chunk IDs
    parent_chunk_id: Optional[str] = None  # ID of parent chunk
    summary_chunk_id: Optional[str] = None  # ID of summary chunk (if exists)
    level: str = "child"  # child, parent, summary

class MultiGranularityChunking(BaseChunkingStrategy):
    """Creates multiple granularity levels of chunks for hierarchical retrieval."""
    
    def __init__(self, config: Optional[HierarchicalChunkingConfig] = None, **kwargs):
        self.config = config or HierarchicalChunkingConfig(
            child_chunk_size=kwargs.get("chunk_size", 128),
            parent_chunk_size=kwargs.get("parent_chunk_size", kwargs.get("chunk_size", 768)),
            child_overlap=kwargs.get("chunk_overlap", 16),
            parent_overlap=kwargs.get("parent_overlap", kwargs.get("chunk_overlap", 64)),
        )
    
    def chunk(self, documents: List[Document], **kwargs) -> List[Chunk]:
        """Create multi-granularity chunks with proper parent-child relationships."""
        return self._create_chunks_with_relationships(documents)
    
    def _create_chunks_with_relationships(self, documents: List[Document]) -> List[Chunk]:
        """Create chunks with proper parent-child relationships."""
        all_chunks = []
        chunk_id_map = {}  # Maps chunk ID to chunk object for linking
        
        for doc in documents:
            # 1. Create child chunks (fine-grained for retrieval)
            child_chunks = self._create_child_chunks(doc)
            
            # 2. Create parent chunks (coarse-grained for context)
            parent_chunks = self._create_parent_chunks(doc, child_chunks)
            
            # 3. Create summary chunks (optional, for very high-level retrieval)
            summary_chunks = []
            if self.config.create_summary_level:
                summary_chunks = self._create_summary_chunks(doc, parent_chunks)
            
            # Store all chunks and create ID mappings
            level_chunks = []
            level_chunks.extend(child_chunks)
            level_chunks.extend(parent_chunks)
            level_chunks.extend(summary_chunks)
            
            # Create ID -> chunk mapping
            for chunk in level_chunks:
                chunk_id_map[chunk.id] = chunk
                all_chunks.append(chunk)
            
            # Establish parent-child relationships
            for child_chunk in child_chunks:
                # Find which parent chunk(s) contain this child
                for parent_chunk in parent_chunks:
                    if self._chunk_is_within_parent(child_chunk, parent_chunk):
                        child_chunk.parent_chunk_id = parent_chunk.id
                        parent_chunk.child_chunk_ids.append(child_chunk.id)
            
            # Link summary chunks to their parent chunks (if applicable)
            if summary_chunks and parent_chunks:
                # Each summary chunk summarizes a group of parent chunks
                # For simplicity, let's make one summary per document for now
                if len(summary_chunks) > 0 and len(parent_chunks) > 0:
                    summary_chunk = summary_chunks[0]
                    summary_chunk.child_chunk_ids = [pc.id for pc in parent_chunks]
                    for pc in parent_chunks:
                        # Optionally link parent to summary (bidirectional)
                        pass  # Could add summary_chunk_id to parent if needed
        
        return all_chunks
    
    def _create_child_chunks(self, document: Document) -> List[Chunk]:
        """Create small child chunks with overlap and separator detection."""
        text = document.content
        if not text.strip():
            return []
        
        chunks = []
        start = 0
        chunk_index = 0
        max_iterations = 5000  # Safety limit
        
        while start < len(text) and chunk_index < max_iterations:
            end = min(start + self.config.child_chunk_size, len(text))
            last_sep = -1
            
            # Try to break at a separator for cleaner chunks
            if end < len(text):
                for sep in self.config.separators:
                    if sep == "":  # Character level
                        break
                    pos = text.rfind(sep, start, end)
                    if pos != -1 and pos > last_sep:
                        last_sep = pos
                        end = pos + len(sep)
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk = Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document.id,
                    content=chunk_text,
                    metadata={**document.metadata, "chunk_level": "child"},
                    chunk_index=chunk_index,
                    filename=document.filename,
                    chunk_level="child"
                )
                chunks.append(chunk)
                chunk_index += 1
            
            if end >= len(text):
                break
            
            # Advance start: use overlap but ENSURE forward progress
            new_start = end - self.config.child_overlap
            if new_start <= start:
                new_start = end  # Force forward progress
            start = max(0, new_start)
        
        return chunks
    
    def _create_parent_chunks(self, document: Document, child_chunks: List[Chunk]) -> List[Chunk]:
        """Create larger chunks for context provision."""
        if not child_chunks:
            return self._create_child_chunks(document)  # Fallback to child-level
        
        # Group child chunks into parent chunks
        parent_chunks = []
        current_parent_children = []
        current_start_idx = 0
        chunk_index = 0
        
        i = 0
        while i < len(child_chunks):
            current_parent_children.append(child_chunks[i])
            
            # Check if we should create a parent chunk
            # Either we've accumulated enough content or we're at the end
            total_length = sum(len(c.content) for c in current_parent_children)
            
            if (total_length >= self.config.parent_chunk_size or 
                i == len(child_chunks) - 1):
                
                # Create parent chunk from the combined content
                combined_content = " ".join([c.content for c in current_parent_children])
                
                parent_chunk = Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document.id,
                    content=combined_content,
                    metadata={**document.metadata, "chunk_level": "parent", "child_count": len(current_parent_children)},
                    chunk_index=chunk_index,
                    filename=document.filename,
                    chunk_level="parent"
                )
                parent_chunks.append(parent_chunk)
                chunk_index += 1
                
                # Reset for next parent chunk
                current_parent_children = []
                current_start_idx = i + 1
            
            i += 1
        
        return parent_chunks
    
    def _create_summary_chunks(self, document: Document, parent_chunks: List[Chunk]) -> List[Chunk]:
        """Create summary chunks for high-level retrieval."""
        if not parent_chunks:
            return []
        
        # For now, create a simple extractive summary
        # In production, this could use an LLM for abstractive summarization
        combined_text = " ".join([p.content for p in parent_chunks])
        
        # Simple extractive: take first few sentences or use scoring
        sentences = re.split(r'[.!?]+', combined_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Take first N sentences that fit in summary size
        summary_sentences = []
        current_length = 0
        
        for sentence in sentences:
            sentence_with_space = sentence + ". "
            current_length += len(sentence_with_space)
            if current_length <= self.config.summary_chunk_size:
                summary_sentences.append(sentence)
            else:
                break
        
        if not summary_sentences:
            # Fallback: just take beginning of text
            summary_text = combined_text[:self.config.summary_chunk_size].strip()
        else:
            summary_text = ". ".join(summary_sentences) + ("." if summary_sentences else "")
        
        if summary_text.strip():
            summary_chunk = Chunk(
                id=str(uuid.uuid4()),
                document_id=document.id,
                content=summary_text,
                metadata={**document.metadata, "chunk_level": "summary", "source_sentences": len(summary_sentences)},
                chunk_index=0,
                filename=document.filename,
                chunk_level="summary"
            )
            return [summary_chunk]
        
        return []
    
    def _chunk_is_within_parent(self, child_chunk: Chunk, parent_chunk: Chunk) -> bool:
        """Check if a child chunk is contained within a parent chunk."""
        # Simple approach: check if child content is substring of parent content
        # In reality, we'd want to check character positions in the original document
        return child_chunk.content in parent_chunk.content

# Register the strategy
@StrategyRegistry.register("chunking", "multigranularity")
class MultiGranularityChunkingAlias(MultiGranularityChunking):
    pass

# Also register as hierarchical for clarity
@StrategyRegistry.register("chunking", "hierarchical")
class HierarchicalChunkingAlias(MultiGranularityChunking):
    pass

from . import image_chunking  # noqa: F401, E402