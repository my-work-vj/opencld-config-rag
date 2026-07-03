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
    """Generate embeddings via LiteLLM proxy."""

    def __init__(self, **kwargs):
        self.client = LiteLLMClient.get_client().client
        self.model = kwargs.get("model", os.getenv("EMBEDDING_MODEL", "nvidia-embed"))
        self.dimensions = kwargs.get("dimensions", 2048)

    def embed(self, chunks: List[Chunk], **kwargs) -> List[EmbeddingVector]:
        model = kwargs.get("model", self.model)
        batch_size = kwargs.get("batch_size", 32)
        input_type = kwargs.get("input_type", "passage")

        all_vectors = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.content for c in batch]

            try:
                kwargs_body = {}
                if input_type:
                    kwargs_body["extra_body"] = {"input_type": input_type, "encoding_format": "float"}

                resp = self.client.embeddings.create(
                    model=model,
                    input=texts,
                    **kwargs_body,
                )
                for chunk, data in zip(batch, resp.data):
                    all_vectors.append(EmbeddingVector(
                        chunk=chunk,
                        vector=data.embedding,
                    ))
            except Exception as e:
                logger.error(f"Embedding batch error: {e}")
                # Return zero vectors for failed batch
                for chunk in batch:
                    all_vectors.append(EmbeddingVector(
                        chunk=chunk,
                        vector=[0.0] * self.dimensions,
                    ))

        return all_vectors

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