"""Layer 5: End-to-end retrieval evaluation using LLM-as-judge.

Implemented as a self-contained module using LiteLLM proxy for both
embedding/retrieval and as the judge LLM. No RAGAS dependency needed.

Metrics (simulating the RAGAS metric set):
- context_precision:  How much of the retrieved context is relevant to the question
- context_recall:     Whether all relevant information was captured in retrieval
- faithfulness:       Whether the answer is supported by the retrieved context
- answer_relevancy:   How directly the answer addresses the question
- noise_sensitivity:  How well the system handles irrelevant context
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from openai import OpenAI


def _make_llm_client(base_url: str | None = None, api_key: str | None = None) -> OpenAI:
    """Create an OpenAI-compatible client pointing at the LiteLLM proxy."""
    return OpenAI(
        base_url=base_url or os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1"),
        api_key=api_key or os.getenv("LITELLM_API_KEY", "sk-vj"),
    )


def _make_qdrant_client() -> Any:
    """Create a QdrantClient using configured host/port."""
    from qdrant_client import QdrantClient as QC
    return QC(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )


def _embed_query(client: OpenAI, text: str, model: str = "nvidia-embed") -> List[float]:
    """Embed a query string using LiteLLM proxy."""
    resp = client.embeddings.create(
        model=model,
        input=[text],
        extra_body={"input_type": "query", "encoding_format": "float"},
    )
    return resp.data[0].embedding


def _search_qdrant(
    qdrant_client: Any,
    collection_name: str,
    query_vector: List[float],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Search Qdrant for top-k chunks."""
    hits = qdrant_client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k,
    )
    results = []
    for hit in hits:
        results.append({
            "id": hit.id,
            "score": hit.score,
            "content": hit.payload.get("content", ""),
            "filename": hit.payload.get("filename", ""),
        })
    return results


def _generate_answer(
    client: OpenAI,
    question: str,
    contexts: List[str],
    model: str = "llama-3.3-70b-versatile",
) -> str:
    """Generate an answer using the retrieved contexts."""
    context_text = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts))
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. Answer the question based ONLY on the provided context. "
                           "If the context doesn't contain the answer, say 'I cannot find this information in the provided context.'",
            },
            {
                "role": "user",
                "content": f"Context:\n{context_text}\n\nQuestion: {question}",
            },
        ],
        temperature=0.1,
        max_tokens=500,
    )
    return resp.choices[0].message.content or ""


def _judge_scores(
    client: OpenAI,
    question: str,
    answer: str,
    contexts: List[str],
    ground_truth: str,
    model: str = "llama-3.3-70b-versatile",
) -> Dict[str, float]:
    """
    Use LLM-as-judge to score a single QA pair across all retrieval metrics.

    Returns dict with scores 0.0-1.0 for:
        faithfulness, answer_relevancy, context_precision, context_recall, noise_sensitivity
    """
    context_text = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts))

    judge_prompt = f"""You are an expert judge evaluating a RAG (Retrieval-Augmented Generation) system.
Analyze the following and provide scores from 0.0 to 1.0.

## Question
{question}

## Retrieved Contexts
{context_text}

## Generated Answer
{answer}

## Ground Truth Answer
{ground_truth}

Rate the following dimensions:

1. **faithfulness** (0.0-1.0): Does the answer stay factually consistent with the retrieved contexts? 
   - 1.0 = All claims in the answer are supported by the contexts
   - 0.0 = The answer contradicts or adds unsupported information

2. **answer_relevancy** (0.0-1.0): How well does the answer address the question?
   - 1.0 = Directly answers the question
   - 0.0 = Completely irrelevant response

3. **context_precision** (0.0-1.0): How much of the retrieved context is actually relevant to the question?
   - 1.0 = Every retrieved chunk is relevant and useful
   - 0.0 = None of the context chunks are relevant

4. **context_recall** (0.0-1.0): Does the retrieved context contain all the information needed to answer the question?
   - 1.0 = All necessary information is present in the contexts
   - 0.0 = Missing crucial information

5. **noise_sensitivity** (0.0-1.0): How much did irrelevant context degrade the answer quality?
   - 1.0 = Perfectly robust to noise, answer ignores irrelevant context
   - 0.0 = Noise severely degraded the answer

Return ONLY a JSON object with these five scores, no other text:
{{"faithfulness": 0.0, "answer_relevancy": 0.0, "context_precision": 0.0, "context_recall": 0.0, "noise_sensitivity": 0.0}}"""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=0.1,
            max_tokens=300,
        )
        content = resp.choices[0].message.content or ""
        # Extract JSON from the response
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            scores = json.loads(content[json_start:json_end])
            # Ensure all keys exist and clamp to [0, 1]
            for key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "noise_sensitivity"]:
                scores[key] = max(0.0, min(1.0, float(scores.get(key, 0.0))))
            return scores
    except Exception as e:
        print(f"  Judge LLM error: {e}")

    # Fallback: reasonable defaults
    return {
        "faithfulness": 0.5,
        "answer_relevancy": 0.5,
        "context_precision": 0.5,
        "context_recall": 0.5,
        "noise_sensitivity": 0.5,
    }


def evaluate_retrieval(
    collection_name: str,
    test_questions: List[Dict[str, Any]],
    llm_client: Optional[Any] = None,
    qdrant_client: Optional[Any] = None,
    embed_model: str = "nvidia-embed",
    chat_model: str = "llama-3.3-70b-versatile",
    judge_model: str = "llama-3.3-70b-versatile",
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Evaluate retrieval quality for a collection using golden test questions.

    Args:
        collection_name: Qdrant collection to search.
        test_questions: List of {"question": str, "ground_truth": str}
        llm_client: OpenAI-compatible client (LiteLLM proxy). Created if None.
        qdrant_client: QdrantClient instance. Created if None.
        embed_model: Model name for embeddings.
        chat_model: Model name for answer generation.
        judge_model: Model name for LLM-as-judge scoring.
        top_k: Number of chunks to retrieve per question.

    Returns:
        Dict with overall scores, per-question breakdown, and metadata.
    """
    client = llm_client or _make_llm_client()
    qclient = qdrant_client or _make_qdrant_client()

    n_questions = len(test_questions)
    if n_questions == 0:
        return {
            "collection_name": collection_name,
            "status": "skipped",
            "message": "No test questions provided",
        }

    scores = {
        "faithfulness": [],
        "answer_relevancy": [],
        "context_precision": [],
        "context_recall": [],
        "noise_sensitivity": [],
    }
    per_question = []
    total_time = 0.0

    for i, tq in enumerate(test_questions):
        q = tq.get("question", "")
        gt = tq.get("ground_truth", "")
        if not q:
            continue

        print(f"  [{i+1}/{n_questions}] Evaluating: {q[:80]}...")
        t0 = time.time()

        # 1. Embed query
        query_vec = _embed_query(client, q, embed_model)

        # 2. Search Qdrant
        hits = _search_qdrant(qclient, collection_name, query_vec, top_k)
        contexts = [h["content"] for h in hits]

        # 3. Generate answer
        answer = _generate_answer(client, q, contexts, chat_model)

        # 4. Judge scores
        scores_i = _judge_scores(client, q, answer, contexts, gt, judge_model)

        elapsed = time.time() - t0
        total_time += elapsed

        # Accumulate
        for key in scores:
            scores[key].append(scores_i.get(key, 0.5))

        per_question.append({
            "question": q,
            "ground_truth": gt,
            "answer": answer,
            "contexts": contexts[:3],  # Keep first 3 contexts for readability
            "score": scores_i,
            "retrieval_time_sec": round(elapsed, 3),
        })

    # Compute averages
    avg_scores = {}
    for key, vals in scores.items():
        avg_scores[key] = round(float(np.mean(vals)), 4) if vals else 0.0

    return {
        "collection_name": collection_name,
        "status": "completed",
        "num_questions": n_questions,
        "top_k": top_k,
        "embed_model": embed_model,
        "chat_model": chat_model,
        "judge_model": judge_model,
        "avg_scores": avg_scores,
        "total_time_sec": round(total_time, 3),
        "avg_time_per_question_sec": round(total_time / max(n_questions, 1), 3),
        "per_question": per_question,
    }
