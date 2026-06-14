"""Retrieval strategies — Naive, Vector, and Hybrid RAG."""

import os
import math
import re
import logging
from collections import Counter

from dotenv import load_dotenv

from core.base_strategies import (
    BaseRetrievalStrategy,
    BaseKnowledgeStoreStrategy,
    KnowledgeStoreHandle,
    Chunk,
    RetrievedChunk,
)
from core.registry import StrategyRegistry
from strategies.embedding import LiteLLMClient

load_dotenv()
logger = logging.getLogger(__name__)


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: list[Chunk] = []
        self.avg_doc_len: float = 0.0
        self.N: int = 0
        self.doc_lens: list[int] = []
        self.df: Counter = Counter()
        self.tf: list[Counter] = []
        self._built = False

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r'\w+', text.lower())

    def build(self, chunks: list[Chunk]) -> None:
        self.corpus = chunks
        self.N = len(chunks)
        self.doc_lens = []
        self.tf = []
        for chunk in chunks:
            terms = self._tokenize(chunk.content)
            self.doc_lens.append(len(terms))
            term_counts = Counter(terms)
            self.tf.append(term_counts)
            for term in set(terms):
                self.df[term] += 1
        self.avg_doc_len = sum(self.doc_lens) / max(self.N, 1)
        self._built = True

    def score(self, query: str, doc_idx: int) -> float:
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
    rrf_scores: dict[str, dict] = {}
    for rank, r in enumerate(vector_results):
        key = r.chunk.content[:200]
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
    sorted_items = sorted(rrf_scores.values(), key=lambda x: x["score"], reverse=True)
    return [
        RetrievedChunk(
            chunk=item["chunk"],
            score=item["score"],
            retrieval_method="+".join(set(item["methods"])),
        )
        for item in sorted_items[:top_k]
    ]


@StrategyRegistry.register("retrieval", "naive_rag")
class NaiveRAGRetrieval(BaseRetrievalStrategy):
    def __init__(self, **kwargs):
        self.embed_client = LiteLLMClient.get_client().client
        self.embed_model = kwargs.get("model", os.getenv("EMBEDDING_MODEL", "nvidia-embed"))

    def _embed_query(self, query: str) -> list[float]:
        resp = self.embed_client.embeddings.create(
            model=self.embed_model,
            input=[query],
            extra_body={"input_type": "query", "encoding_format": "float"},
        )
        return resp.data[0].embedding

    def retrieve(
        self,
        query: str,
        store: KnowledgeStoreHandle,
        knowledge_store_strategy: BaseKnowledgeStoreStrategy,
        top_k: int = 5,
        **kwargs,
    ) -> list[RetrievedChunk]:
        logger.info(f"[NaiveRAG] Query: '{query[:80]}...' | top_k={top_k}")
        query_vec = self._embed_query(query)
        results = knowledge_store_strategy.search(query_vec, store, top_k=top_k, **kwargs)
        logger.info(f"[NaiveRAG] Retrieved {len(results)} chunks")
        return results


@StrategyRegistry.register("retrieval", "vector_rag")
class VectorRAGRetrieval(BaseRetrievalStrategy):
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
                clean = re.sub(r'^\d+[\.\)]\s*', '', line)
                queries.append(clean)
        return queries[:num_queries]

    def retrieve(
        self,
        query: str,
        store: KnowledgeStoreHandle,
        knowledge_store_strategy: BaseKnowledgeStoreStrategy,
        top_k: int = 5,
        **kwargs,
    ) -> list[RetrievedChunk]:
        use_hyde = kwargs.get("use_hyde", False)
        query_rewrite = kwargs.get("query_rewrite", False)
        top_k_rerank = kwargs.get("top_k_rerank", top_k * 2)

        if use_hyde:
            embed_query = self._generate_hyde(query)
            logger.info(f"[VectorRAG] Using HyDE ({len(embed_query)} chars)")
        elif query_rewrite:
            embed_query = query
            logger.info("[VectorRAG] Query expansion enabled")
        else:
            embed_query = query

        query_vec = self._embed_query(embed_query)
        results = knowledge_store_strategy.search(
            query_vec, store, top_k=top_k_rerank, **kwargs
        )

        if query_rewrite and not use_hyde:
            all_results = {r.chunk.content[:200]: r for r in results}
            try:
                for eq in self._expand_query(query):
                    eq_vec = self._embed_query(eq)
                    extra = knowledge_store_strategy.search(
                        eq_vec, store, top_k=top_k, **kwargs
                    )
                    for r in extra:
                        key = r.chunk.content[:200]
                        if key not in all_results:
                            all_results[key] = r
                results = list(all_results.values())
            except Exception as e:
                logger.warning(f"[VectorRAG] Query expansion failed: {e}")

        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:top_k]
        logger.info(f"[VectorRAG] Retrieved {len(results)} chunks")
        return results


@StrategyRegistry.register("retrieval", "hybrid_bm25_vector")
class HybridBM25VectorRetrieval(BaseRetrievalStrategy):
    def __init__(self, **kwargs):
        self.embed_client = LiteLLMClient.get_client().client
        self.embed_model = kwargs.get("model", os.getenv("EMBEDDING_MODEL", "nvidia-embed"))
        self.bm25_k1 = kwargs.get("bm25_k1", 1.5)
        self.bm25_b = kwargs.get("bm25_b", 0.75)
        self.dense_weight = kwargs.get("dense_weight", 0.5)
        self.sparse_weight = kwargs.get("sparse_weight", 0.5)
        self.rrf_k = kwargs.get("rrf_k", 60)
        self.bm25 = BM25Index(k1=self.bm25_k1, b=self.bm25_b)
        self._bm25_built = False
        self._store_key = ""

    def _embed_query(self, query: str) -> list[float]:
        resp = self.embed_client.embeddings.create(
            model=self.embed_model,
            input=[query],
            extra_body={"input_type": "query", "encoding_format": "float"},
        )
        return resp.data[0].embedding

    def _ensure_bm25(
        self,
        store: KnowledgeStoreHandle,
        knowledge_store_strategy: BaseKnowledgeStoreStrategy,
    ) -> None:
        store_key = store.collection_name
        if not self._bm25_built or self._store_key != store_key:
            chunks = knowledge_store_strategy.scroll_chunks(store)
            if chunks:
                self.bm25.build(chunks)
                self._bm25_built = True
                self._store_key = store_key

    def retrieve(
        self,
        query: str,
        store: KnowledgeStoreHandle,
        knowledge_store_strategy: BaseKnowledgeStoreStrategy,
        top_k: int = 5,
        **kwargs,
    ) -> list[RetrievedChunk]:
        dense_weight = kwargs.get("dense_weight", self.dense_weight)
        sparse_weight = kwargs.get("sparse_weight", self.sparse_weight)
        rrf_k = kwargs.get("rrf_k", self.rrf_k)
        sparse_top_k = kwargs.get("sparse_top_k", top_k * 3)

        logger.info(f"[HybridRAG] Query: '{query[:80]}...'")

        query_vec = self._embed_query(query)
        dense_results = knowledge_store_strategy.search(
            query_vec, store, top_k=sparse_top_k, **kwargs
        )

        sparse_results = []
        try:
            self._ensure_bm25(store, knowledge_store_strategy)
            if self._bm25_built:
                sparse_results = self.bm25.search(query, top_k=sparse_top_k)
        except Exception as e:
            logger.warning(f"[HybridRAG] BM25 failed: {e}")

        fused = reciprocal_rank_fusion(
            vector_results=dense_results,
            sparse_results=sparse_results,
            k=rrf_k,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            top_k=top_k,
        )
        logger.info(
            f"[HybridRAG] {len(dense_results)} dense + {len(sparse_results)} sparse "
            f"→ {len(fused)} fused"
        )
        return fused
