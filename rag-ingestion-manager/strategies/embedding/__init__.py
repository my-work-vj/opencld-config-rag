"""Embedding strategies for dense and sparse vector generation."""

import os
import logging
import re
import math
from typing import Optional, List, Dict, Any
from collections import Counter

from openai import OpenAI
from dotenv import load_dotenv

from core.base_strategies import BaseEmbeddingStrategy, BaseSparseEmbeddingStrategy, Chunk, EmbeddingVector, SparseVector
from core.registry import StrategyRegistry

load_dotenv()
logger = logging.getLogger(__name__)

# ============================
# DENSE EMBEDDING STRATEGIES
# ============================

class LiteLLMClient:
    """Shared LiteLLM client."""
    _instance: Optional["LiteLLMClient"] = None

    def __init__(self):
        self.base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
        self.api_key = os.getenv("LITELLM_API_KEY", "sk-vj")
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    @classmethod
    def get_client(cls) -> "LiteLLMClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

@StrategyRegistry.register("embedding", "litellm_embedding")
class LiteLLMEmbedding(BaseEmbeddingStrategy):
    """Generate dense embeddings via LiteLLM (text + multimodal image inputs)."""

    def __init__(self, **kwargs):
        self.client = LiteLLMClient.get_client().client
        self.model = kwargs.get("model", os.getenv("EMBEDDING_MODEL", "nvidia-embed"))
        self.dimensions = kwargs.get("dimensions")
        if not self.dimensions:
            try:
                from services.litellm_model_info import get_embedding_model_info
                self.dimensions = get_embedding_model_info(self.model)["output_dimensions"]
            except Exception:
                self.dimensions = int(os.getenv("DEFAULT_VECTOR_SIZE", "2048"))

    def _zero_vector(self) -> list[float]:
        return [0.0] * int(self.dimensions or 2048)

    def _embed_text_batch(
        self,
        batch: list[Chunk],
        model: str,
        input_type: str,
    ) -> dict[str, list[float]]:
        texts = [c.content for c in batch]
        vectors: dict[str, list[float]] = {}
        try:
            resp = self.client.embeddings.create(
                model=model,
                input=texts,
                extra_body={"input_type": input_type, "encoding_format": "float", "modality": "text"},
            )
            for chunk, data in zip(batch, resp.data):
                vectors[chunk.id] = data.embedding
                if data.embedding:
                    self.dimensions = len(data.embedding)
        except Exception as exc:
            logger.error("Text embedding batch error: %s", exc)
            for chunk in batch:
                vectors[chunk.id] = self._zero_vector()
        return vectors

    def _embed_image_chunk(self, chunk: Chunk, model: str, input_type: str) -> list[float]:
        from services.modality import path_to_data_url

        image_path = chunk.metadata.get("image_path") or chunk.metadata.get("path")
        if not image_path:
            logger.error("Image chunk %s is missing image_path metadata", chunk.id)
            return self._zero_vector()

        try:
            data_url = path_to_data_url(image_path)
            resp = self.client.embeddings.create(
                model=model,
                input=[data_url],
                extra_body={
                    "input_type": input_type,
                    "modality": "image",
                    "encoding_format": "float",
                },
            )
            vector = resp.data[0].embedding
            if vector:
                self.dimensions = len(vector)
            return vector
        except Exception as exc:
            logger.error("Image embedding error for %s: %s", image_path, exc)
            return self._zero_vector()

    def embed(self, chunks: List[Chunk], **kwargs) -> List[EmbeddingVector]:
        if not chunks:
            return []

        model = kwargs.get("model", self.model)
        batch_size = kwargs.get("batch_size", 32)
        input_type = kwargs.get("input_type", "passage")

        vectors_by_id: dict[str, list[float]] = {}
        text_chunks = [c for c in chunks if c.metadata.get("modality") != "image"]
        image_chunks = [c for c in chunks if c.metadata.get("modality") == "image"]

        for i in range(0, len(text_chunks), batch_size):
            batch = text_chunks[i:i + batch_size]
            vectors_by_id.update(self._embed_text_batch(batch, model, input_type))

        for chunk in image_chunks:
            vectors_by_id[chunk.id] = self._embed_image_chunk(chunk, model, input_type)

        return [
            EmbeddingVector(
                chunk=chunk,
                vector=vectors_by_id.get(chunk.id, self._zero_vector()),
            )
            for chunk in chunks
        ]

# ============================
# SPARSE (BM25-like) EMBEDDING STRATEGIES
# ============================

class SimpleTokenizer:
    """Simple tokenizer for BM25-style processing."""
    
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize text into lowercase alphanumeric tokens."""
        if not text:
            return []
        # Extract alphanumeric tokens and convert to lowercase
        return re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())

class BM25Encoder:
    """Simple BM25-like encoder for sparse vector generation."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs = {}  # term -> document frequency
        self.idf = {}  # term -> inverse document frequency
        self.doc_lengths = []  # length of each document
        self.avgdl = 0  # average document length
        self.doc_count = 0
        self.vocabulary = {}  # term -> term_id
        self.next_term_id = 1
    
    def fit(self, documents: List[str]):
        """Fit the BM25 model on a collection of documents."""
        # Tokenize all documents
        tokenized_docs = [SimpleTokenizer.tokenize(doc) for doc in documents]
        self.doc_count = len(tokenized_docs)
        
        # Calculate document frequencies and lengths
        for tokens in tokenized_docs:
            self.doc_lengths.append(len(tokens))
            # Count term frequency in this document
            freq_in_doc = Counter(tokens)
            # Update document frequency (count documents containing each term)
            for term in freq_in_doc:
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1
        
        # Calculate average document length
        self.avgdl = sum(self.doc_lengths) / max(self.doc_count, 1)
        
        # Calculate IDF for each term
        for term, df in self.doc_freqs.items():
            # IDF = log((N - df + 0.5) / (df + 0.5) + 1)
            self.idf[term] = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1)
        
        # Create vocabulary mapping (term -> ID)
        for term in sorted(self.doc_freqs.keys()):
            if term not in self.vocabulary:
                self.vocabulary[term] = self.next_term_id
                self.next_term_id += 1
    
    def encode(self, text: str) -> dict[int, float]:
        """Encode a single text's BM25 weights."""
        if not text:
            return {}
        
        tokens = SimpleTokenizer.tokenize(text)
        if not tokens:
            return {}
        
        # Term frequency in this document
        tf = Counter(tokens)
        doc_len = len(tokens)
        
        # Calculate BM25-like weights
        weights = {}
        for term, term_freq in tf.items():
            if term in self.idf and term in self.vocabulary:
                # BM25 formula: IDF * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (dl / avgdl)))
                idf = self.idf[term]
                numerator = term_freq * (self.k1 + 1)
                denominator = term_freq + self.k1 * (1 - self.b + self.b * (doc_len / max(self.avgdl, 1)))
                weight = idf * (numerator / denominator)
                
                term_id = self.vocabulary[term]
                weights[term_id] = weight
        
        return weights

@StrategyRegistry.register("embedding", "bm25_sparse")
class BM25SparseEmbedding(BaseSparseEmbeddingStrategy):
    """Generate sparse (BM25-like) embeddings for keyword matching."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.encoder = BM25Encoder(k1=k1, b=b)
        self.is_fitted = False
        # We'll fit on-the-fly or use a pre-trained vocabulary
        # For simplicity in this implementation, we'll build vocab from input
        # In production, you'd want to pretrain on a representative corpus
    
    def embed_sparse(self, chunks: List[Chunk], **kwargs) -> List[SparseVector]:
        """Generate sparse vectors for chunks using BM25-like scoring."""
        if not chunks:
            return []
        
        # Extract text content
        texts = [chunk.content for chunk in chunks]
        
        # Fit or update the encoder with current batch
        # In a production system, you'd use a pre-trained/vocabulary from corpus
        self.encoder.fit(texts)
        
        # Encode each chunk
        sparse_vectors = []
        for chunk in chunks:
            weights = self.encoder.encode(chunk.content)
            sparse_vectors.append(SparseVector(chunk=chunk, weights=weights))
        
        return sparse_vectors

# Alternative: Hashing-based sparse encoding for fixed vocabulary size
class HashingSparseEncoder:
    """Hashing-based sparse encoder for fixed-size vocabulary."""
    
    def __init__(self, vocab_size: int = 10000):
        self.vocab_size = vocab_size
    
    def encode(self, text: str) -> dict[int, float]:
        """Encode text using hashing trick for sparse representation."""
        if not text:
            return {}
        
        tokens = SimpleTokenizer.tokenize(text)
        if not tokens:
            return {}
        
        # Count term frequencies
        tf = Counter(tokens)
        total_terms = len(tokens)
        
        # Hash each term to a fixed vocabulary space
        weights = {}
        for term, freq in tf.items():
            # Simple hash function - in production use something like murmurhash
            hash_value = hash(term) % self.vocab_size
            # Ensure non-negative
            if hash_value < 0:
                hash_value += self.vocab_size
            
            # Term frequency weight (could be TF-IDF, but we'll use normalized TF for simplicity)
            weight = freq / max(total_terms, 1)
            
            # Combine weights if multiple terms hash to same index (handle collisions)
            if hash_value in weights:
                weights[hash_value] += weight
            else:
                weights[hash_value] = weight
        
        return weights

@StrategyRegistry.register("embedding", "hashing_sparse")
class HashingSparseEmbedding(BaseSparseEmbeddingStrategy):
    """Generate sparse embeddings using the hashing trick."""
    
    def __init__(self, vocab_size: int = 10000):
        self.encoder = HashingSparseEncoder(vocab_size=vocab_size)
    
    def embed_sparse(self, chunks: List[Chunk], **kwargs) -> List[SparseVector]:
        """Generate sparse vectors using hashing trick."""
        if not chunks:
            return []
        
        sparse_vectors = []
        for chunk in chunks:
            weights = self.encoder.encode(chunk.content)
            sparse_vectors.append(SparseVector(chunk=chunk, weights=weights))
        
        return sparse_vectors

# Register aliases for clarity
@StrategyRegistry.register("embedding", "sparse_bm25")
class BM25SparseAlias(BM25SparseEmbedding):
    pass

@StrategyRegistry.register("embedding", "sparse_hashing")
class HashingSparseAlias(HashingSparseEmbedding):
    pass

# Also register under "sparse_embedding" stage (for multi-index pipeline routing)
StrategyRegistry._strategies.setdefault("sparse_embedding", {})["bm25_sparse"] = BM25SparseEmbedding
StrategyRegistry._strategies.setdefault("sparse_embedding", {})["hashing_sparse"] = HashingSparseEmbedding