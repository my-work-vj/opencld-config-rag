"""Retrieval strategies — Naive RAG, Vector RAG, and Hybrid RAG (BM25 + Vector)."""

import os
import math
import re
import logging
from collections import Counter
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from core.base_strategies import (
    BaseRetrievalStrategy, Chunk, RetrievedChunk, Document, EmbeddingVector,
)
from core.registry import StrategyRegistry
from strategies.embedding import LiteLLMClient

load_dotenv()
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# Shared utilities
# ──────────────────────────────────────────

class BM25Index:
    """Simple in-memory BM25 index for sparse retrieval.

    Maintains term frequencies, document frequencies, and computes
    BM25 scores for queries against the indexed corpus.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: list[Chunk] = []
        self.avg_doc_len: float = 0.0
        self.N: int = 0
        self.doc_lens: list[int] = []
        self.df: Counter = Counter()       # document frequency per term
        self.tf: list[Counter] = []        # term frequency per document
        self._built = False

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r'\w+', text.lower())

    def build(self, chunks: list[Chunk]) -> None:
        """Build BM25 index from chunks."""
        self.corpus = chunks
        self.N = len(chunks)
        self.doc_lens = []
        self.tf = []

        all_terms = Counter()
        for chunk in chunks:
            terms = self._tokenize(chunk.content)
            self.doc_lens.append(len(terms))
            term_counts = Counter(terms)
            self.tf.append(term_counts)
            for term in set(terms):
                self.df[term] += 1
                all_terms[term] += 1

        self.avg_doc_len = sum(self.doc_lens) / max(self.N, 1)
        self._built = True
        logger.info(f"BM25 index built: {self.N} docs, {len(self.df)} unique terms, avg_len={self.avg_doc_len:.1f}")

    def score(self, query: str, doc_idx: int) -> float:
        """Compute BM25 score for a query against document at doc_idx."""
        if not self._built or self.N == 0:
            return 0.0

        query_terms = self._tokenize(query)
        if not query_terms:
            return 0.0

        dl = self.doc_lens[doc_idx]
        score = 0.0
        doc_tf = self.tf[doc_idx]

        for term in query_terms:
            tf = doc_tf.get(term, 0)
            if tf == 0:
                continue
            df = self.df.get(term, 0)
            idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1.0)
            tf_norm = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * (dl / self.avg_doc_len)))
            score += idf * tf_norm

        return score

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Search BM25 index and return top-k results."""
        scored = [(self.score(query, i), i) for i in range(self.N)]
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, idx in scored[:top_k]:
            if score > 0:
                results.append(RetrievedChunk(
                    chunk=self.corpus[idx],
                    score=score,
                    retrieval_method="bm25",
                ))
        return results


def reciprocal_rank_fusion(
    vector_results: list[RetrievedChunk],
    sparse_results: list[RetrievedChunk],
    k: int = 60,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Reciprocal Rank Fusion combining dense and sparse results."""

    # Build RRF score map keyed by chunk content (to deduplicate)
    rrf_scores: dict[str, dict] = {}

    for rank, r in enumerate(vector_results):
        key = r.chunk.content[:200]  # use content prefix as key
        if key not in rrf_scores:
            rrf_scores[key] = {"chunk": r.chunk, "score": 0, "methods": []}
        rrf_scores[key]["score"] += dense_weight * (1.0 / (k + rank + 1))
        rrf_scores[key]["methods"].append("vector")

    for rank, r in enumerate(sparse_results):
        key = r.chunk.content[:200]
        if key not in rrf_scores:
            rrf_scores[key] = {"chunk": r.chunk, "score": 0, "methods": []}
        rrf_scores[key]["score"] += sparse_weight * (1.0 / (k + rank + 1))
        rrf_scores[key]["methods"].append("bm25")

    # Sort by fused score
    sorted_items = sorted(rrf_scores.values(), key=lambda x: x["score"], reverse=True)

    return [
        RetrievedChunk(
            chunk=item["chunk"],
            score=item["score"],
            retrieval_method="+".join(set(item["methods"])),
        )
        for item in sorted_items[:top_k]
    ]


# ──────────────────────────────────────────
# 1. Naive RAG — single-pass dense retrieval
# ──────────────────────────────────────────

@StrategyRegistry.register("retrieval", "naive_rag")
class NaiveRAGRetrieval(BaseRetrievalStrategy):
    """Naive RAG: single-pass dense vector retrieval, no rewriting, no reranking.

    This is the simplest RAG approach: embed the raw query, find similar chunks,
    and return them directly. Fastest path, lowest quality ceiling.
    """

    def __init__(self, **kwargs):
        self.embed_client = LiteLLMClient.get_client().client
        self.embed_model = kwargs.get("model", os.getenv("EMBEDDING_MODEL", "nvidia-embed"))
        self.embed_dims = kwargs.get("embed_dimensions", 2048)

    def _embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        resp = self.embed_client.embeddings.create(
            model=self.embed_model,
            input=[query],
            extra_body={"input_type": "query", "encoding_format": "float"},
        )
        return resp.data[0].embedding

    def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        """Naive: embed raw query → vector search → return top-k."""
        from strategies.indexing import QdrantIndexing

        logger.info(f"[NaiveRAG] Query: '{query[:80]}...' | top_k={top_k}")

        query_vec = self._embed_query(query)

        indexer = QdrantIndexing()
        results = indexer.search(
            query_vector=query_vec,
            top_k=top_k,
            collection_name=kwargs.get("collection_name", "rag_documents"),
        )

        logger.info(f"[NaiveRAG] Retrieved {len(results)} chunks")
        return results


# ──────────────────────────────────────────
# 2. Vector RAG — dense retrieval with HyDE / query expansion
# ──────────────────────────────────────────

@StrategyRegistry.register("retrieval", "vector_rag")
class VectorRAGRetrieval(BaseRetrievalStrategy):
    """Vector RAG: dense retrieval with optional HyDE query rewriting.

    Features:
    - Optional HyDE: generate a hypothetical answer, embed that instead
    - Optional multi-query expansion: generate sub-queries, retrieve for each
    - Returns more candidates (top_k_rerank) for downstream reranking
    """

    def __init__(self, **kwargs):
        self.embed_client = LiteLLMClient.get_client().client
        self.llm_client = LiteLLMClient.get_client().client
        self.embed_model = kwargs.get("model", os.getenv("EMBEDDING_MODEL", "nvidia-embed"))
        self.llm_model = kwargs.get("hyde_model", os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"))

    def _embed_query(self, query: str) -> list[float]:
        resp = self.embed_client.embeddings.create(
            model=self.embed_model,
            input=[query],
            extra_body={"input_type": "query", "encoding_format": "float"},
        )
        return resp.data[0].embedding

    def _generate_hyde(self, query: str) -> str:
        """Generate a hypothetical document for HyDE."""
        system_prompt = (
            "You are generating a hypothetical document snippet that would "
            "perfectly answer the user's question. Write a concise, informative "
            "paragraph (3-5 sentences) that directly answers the question."
        )
        resp = self.llm_client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.5,
            max_tokens=512,
        )
        return resp.choices[0].message.content or query

    def _expand_query(self, query: str, num_queries: int = 3) -> list[str]:
        """Generate multiple sub-queries from the original query."""
        system_prompt = (
            f"Generate {num_queries} different versions of the given query "
            "to improve retrieval recall. Each should capture a different aspect. "
            "Return one per line, numbered. Keep them concise."
        )
        resp = self.llm_client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.7,
            max_tokens=512,
        )
        content = resp.choices[0].message.content or ""
        queries = []
        for line in content.strip().split("\n"):
            line = line.strip()
            if line and any(c.isalpha() for c in line):
                # Strip numbering
                clean = re.sub(r'^\d+[\.\)]\s*', '', line)
                queries.append(clean)
        return queries[:num_queries]

    def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        """Vector RAG: optionally rewrite query, then dense retrieval."""
        from strategies.indexing import QdrantIndexing

        use_hyde = kwargs.get("use_hyde", False)
        query_rewrite = kwargs.get("query_rewrite", False)
        top_k_rerank = kwargs.get("top_k_rerank", top_k * 2)
        collection_name = kwargs.get("collection_name", "rag_documents")

        # Determine the actual query to embed
        if use_hyde:
            hyde_doc = self._generate_hyde(query)
            embed_query = hyde_doc
            logger.info(f"[VectorRAG] Using HyDE (hypothetical doc: {len(hyde_doc)} chars)")
        elif query_rewrite:
            expansions = self._expand_query(query)
            embed_query = query
            logger.info(f"[VectorRAG] Query expanded into {len(expansions)} variations")
        else:
            embed_query = query

        # Embed and search
        query_vec = self._embed_query(embed_query)
        indexer = QdrantIndexing()
        results = indexer.search(
            query_vector=query_vec,
            top_k=top_k_rerank,
            collection_name=collection_name,
        )

        # If we expanded queries, do additional searches and fuse
        if query_rewrite and not use_hyde:
            all_results = {r.chunk.content[:200]: r for r in results}
            try:
                expansions = self._expand_query(query)
                for eq in expansions:
                    eq_vec = self._embed_query(eq)
                    extra = indexer.search(
                        query_vector=eq_vec,
                        top_k=top_k,
                        collection_name=collection_name,
                    )
                    for r in extra:
                        key = r.chunk.content[:200]
                        if key not in all_results:
                            all_results[key] = r
                results = list(all_results.values())
            except Exception as e:
                logger.warning(f"[VectorRAG] Query expansion failed: {e}")

        # Sort by score and take top_k
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:top_k]

        logger.info(f"[VectorRAG] Retrieved {len(results)} chunks (hyde={use_hyde}, rewrite={query_rewrite})")
        return results


# ──────────────────────────────────────────
# 3. Hybrid RAG — dense + sparse with RRF fusion
# ──────────────────────────────────────────

@StrategyRegistry.register("retrieval", "hybrid_bm25_vector")
class HybridBM25VectorRetrieval(BaseRetrievalStrategy):
    """Hybrid RAG: BM25 sparse retrieval + dense vector retrieval with RRF fusion.

    Two parallel retrieval paths:
    1. Dense (vector): semantic similarity via embedding
    2. Sparse (BM25): keyword matching for exact term hits

    Results fused via Reciprocal Rank Fusion (RRF).
    Best quality ceiling, handles both semantic and keyword queries.
    """

    def __init__(self, **kwargs):
        self.embed_client = LiteLLMClient.get_client().client
        self.embed_model = kwargs.get("model", os.getenv("EMBEDDING_MODEL", "nvidia-embed"))
        self.bm25_k1 = kwargs.get("bm25_k1", 1.5)
        self.bm25_b = kwargs.get("bm25_b", 0.75)
        self.dense_weight = kwargs.get("dense_weight", 0.5)
        self.sparse_weight = kwargs.get("sparse_weight", 0.5)
        self.rrf_k = kwargs.get("rrf_k", 60)

        # BM25 index (built from indexed documents)
        self.bm25 = BM25Index(k1=self.bm25_k1, b=self.bm25_b)
        self._bm25_built = False
        self._all_chunks: list[Chunk] = []

    def _load_all_chunks_from_qdrant(self, collection_name: str) -> list[Chunk]:
        """Load all chunks from Qdrant to build BM25 index."""
        from qdrant_client import QdrantClient
        host = os.getenv("QDRANT_HOST", "localhost")
        port = int(os.getenv("QDRANT_PORT", "6333"))
        client = QdrantClient(host=host, port=port)

        try:
            collection_info = client.get_collection(collection_name)
            total = collection_info.points_count
            if total == 0:
                return []

            limit = min(10000, total)
            scroll_result = client.scroll(
                collection_name=collection_name,
                limit=limit,
                with_payload=True,
            )

            chunks = []
            for point in scroll_result[0]:
                payload = point.payload or {}
                chunk = Chunk(
                    id=payload.get("chunk_id", point.id),
                    document_id=payload.get("document_id", ""),
                    content=payload.get("content", ""),
                    metadata={k: v for k, v in payload.items() if k not in ("chunk_id", "document_id", "content", "chunk_index", "filename")},
                    chunk_index=payload.get("chunk_index", 0),
                    filename=payload.get("filename"),
                )
                chunks.append(chunk)
            return chunks
        except Exception as e:
            logger.warning(f"[HybridRAG] Could not load chunks from Qdrant: {e}")
            return []

    def _ensure_bm25(self, collection_name: str) -> None:
        """Build BM25 index if not already built."""
        if not self._bm25_built:
            self._all_chunks = self._load_all_chunks_from_qdrant(collection_name)
            if self._all_chunks:
                self.bm25.build(self._all_chunks)
                self._bm25_built = True

    def _embed_query(self, query: str) -> list[float]:
        resp = self.embed_client.embeddings.create(
            model=self.embed_model,
            input=[query],
            extra_body={"input_type": "query", "encoding_format": "float"},
        )
        return resp.data[0].embedding

    def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        """Hybrid: dense + sparse parallel retrieval → RRF fusion."""
        from strategies.indexing import QdrantIndexing

        collection_name = kwargs.get("collection_name", "rag_documents")
        dense_weight = kwargs.get("dense_weight", self.dense_weight)
        sparse_weight = kwargs.get("sparse_weight", self.sparse_weight)
        rrf_k = kwargs.get("rrf_k", self.rrf_k)
        sparse_top_k = kwargs.get("sparse_top_k", top_k * 3)

        logger.info(f"[HybridRAG] Query: '{query[:80]}...' | dense={dense_weight}, sparse={sparse_weight}, k={rrf_k}")

        # 1. Dense vector search
        query_vec = self._embed_query(query)
        indexer = QdrantIndexing()
        dense_results = indexer.search(
            query_vector=query_vec,
            top_k=sparse_top_k,
            collection_name=collection_name,
        )

        # 2. Ensure BM25 is built, then sparse search
        try:
            self._ensure_bm25(collection_name)
        except Exception as e:
            logger.warning(f"[HybridRAG] BM25 init failed: {e}")

        sparse_results = []
        if self._bm25_built:
            try:
                sparse_results = self.bm25.search(query, top_k=sparse_top_k)
            except Exception as e:
                logger.warning(f"[HybridRAG] BM25 search failed: {e}")

        # 3. RRF fusion
        fused = reciprocal_rank_fusion(
            vector_results=dense_results,
            sparse_results=sparse_results,
            k=rrf_k,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            top_k=top_k,
        )

        logger.info(f"[HybridRAG] Retrieved {len(dense_results)} dense + {len(sparse_results)} sparse → {len(fused)} fused")
        return fused
