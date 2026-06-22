# Ingestion Pipeline Evaluation Plan

> **For Hermes:** Use subagent-driven-development to implement this plan task-by-task.

**Goal:** Build a comprehensive evaluation system for the Multi-RAG ingestion pipeline — measuring extraction quality, chunking quality, embedding quality, pipeline throughput, and end-to-end retrieval quality.

**Architecture:** Layer custom quality metrics on top of existing strategy system + RAGAS/DeepEval for downstream retrieval evaluation. Add a CLI `eval` command + optional API endpoint + scheduled evaluation cron job.

**Tech Stack:** Python, RAGAS (v0.2+), DeepEval, pytest, Qdrant client, LiteLLM proxy (judge LLM)

---

## Table of Contents
1. [Current State & What We Need](#current-state)
2. [Overview of Evaluation Layers](#eval-layers)
3. [Layer 1: Extraction Quality Metrics](#layer-1)
4. [Layer 2: Chunking Quality Metrics](#layer-2)
5. [Layer 3: Embedding Quality Metrics](#layer-3)
6. [Layer 4: Pipeline Throughput & Reliability](#layer-4)
7. [Layer 5: End-to-End Retrieval via RAGAS/DeepEval](#layer-5)
8. [Architecture & Files](#architecture)
9. [Implementation Plan](#impl-plan)
10. [Verification & Testing](#verification)

---

<a name="current-state"></a>
## 1. Current State & What We Need

### Current State
- **Ingestion pipeline works**: kreuzberg → chunking → embedding → Qdrant indexing
- **Strategies**: kreuzberg_ingestion, recursive_chunking / fixed_size_chunking, litellm_embedding, qdrant_indexing
- **Backend**: FastAPI on `:8081`, collection sync via `sync_collection()`
- **Monitor worker**: poll-based sync every 30s

### What We Need
- **Quality gates** that run after each sync cycle
- **Per-stage metrics** reported per collection
- **Historical tracking** to detect regressions
- **CLI command** to manually trigger evaluation on a collection
- **Optional API endpoint** to integrate with CI/CD

---

<a name="eval-layers"></a>
## 2. Overview of Evaluation Layers

```
┌─────────────────────────────────────────────────────┐
│            LAYER 5: End-to-End Retrieval            │
│  RAGAS/DeepEval: Context Precision, Recall,         │
│  Faithfulness, Answer Relevancy                     │
│  Requires: golden test dataset (queries + answers)   │
├─────────────────────────────────────────────────────┤
│            LAYER 4: Pipeline Throughput              │
│  docs/min, chunks/min, latency breakdown,            │
│  failure rate, empty extraction rate                 │
├─────────────────────────────────────────────────────┤
│            LAYER 3: Embedding Quality                │
│  Within-cluster / between-cluster distance ratio,    │
│  dimension utilization, outlier detection            │
├─────────────────────────────────────────────────────┤
│            LAYER 2: Chunking Quality                 │
│  Size distribution, boundary quality,                │
│  overlap accuracy, uniqueness, semantic coherence    │
├─────────────────────────────────────────────────────┤
│            LAYER 1: Extraction Quality               │
│  Success rate, empty extraction rate,                │
│  format coverage, text-to-source ratio               │
└─────────────────────────────────────────────────────┘
```

---

<a name="layer-1"></a>
## 3. Layer 1: Extraction Quality Metrics (kreuzberg)

These run inline during ingestion — collected per file and aggregated per sync.

### Metrics

| Metric | Type | Description | Implementation |
|--------|------|-------------|----------------|
| `extraction_success_rate` | % | % of files that returned non-empty text | `extracted_count / total_files * 100` |
| `empty_extraction_rate` | % | % of files that returned 0 content | `empty_count / total_files * 100` |
| `avg_content_length` | chars | Average chars per extracted doc | `sum(len(doc.content)) / doc_count` |
| `content_length_stdev` | chars | Std dev of content length | `statistics.stdev()` |
| `format_coverage` | set | Which file extensions were handled | `{'.pdf', '.docx', ...}` |
| `error_rate` | % | % of files that threw exceptions | `error_count / total_files * 100` |
| `extraction_time_avg` | ms | Avg time per extraction | `extraction_total_time / total_files` |

### Where to Implement

**New file**: `rag-ingestion-manager/evaluation/extraction_metrics.py`

### Data Collection

Modify `krauzberg_ingestion.py` to return extraction metadata alongside documents:
```python
# Modified return signature
documents: list[Document]
metadata: dict = {
    "extraction_time_ms": ...,
    "file_size": ...,
    "format": ...,
}
```

Or (simpler): collect metrics in `_run_connector_file_ingest` in `collection_sync_service.py` after the pipeline runs, then emit to a metrics store.

---

<a name="layer-2"></a>
## 4. Layer 2: Chunking Quality Metrics

Run after chunking completes — measures the structural quality of chunks.

### Metrics

| Metric | Type | Description | Implementation |
|--------|------|-------------|----------------|
| `avg_chunk_size` | chars | Average chars per chunk | `sum(len(c.content)) / chunk_count` |
| `chunk_size_stdev` | chars | Std dev of chunk size | `statistics.stdev()` |
| `chunk_size_p50/p95/p99` | chars | Percentile distribution | `sorted(list)[index]` |
| `chunks_per_doc` | ratio | Avg chunks per source document | `chunk_count / doc_count` |
| `overflow_chunks` | % | Chunks at max size (likely truncated) | `count(size==max) / total * 100` |
| `empty_chunks` | % | Chunks with 0 content | guard / already prevented |
| `overlap_accuracy` | % | Actual overlap matches configured | measure `chunk[i].end + overlap == chunk[i+1].start` |
| `duplicate_content_rate` | % | Chunks with identical content | `count(duplicates) / total * 100` |

### Where to Implement

**New file**: `rag-ingestion-manager/evaluation/chunking_metrics.py`

### Implementation Pattern

```python
def evaluate_chunks(chunks: list[Chunk], config: dict) -> dict:
    sizes = [len(c.content) for c in chunks]
    return {
        "avg_size": mean(sizes),
        "stdev_size": stdev(sizes) if len(sizes) > 1 else 0,
        "p50": percentile(sizes, 50),
        "p95": percentile(sizes, 95),
        "p99": percentile(sizes, 99),
        "total_chunks": len(chunks),
        "empty_chunks": sum(1 for s in sizes if s == 0),
        "duplicate_content": len(sizes) - len(set(chunk.content for chunk in chunks)),
    }
```

---

<a name="layer-3"></a>
## 5. Layer 3: Embedding Quality Metrics

Run after embedding generation — measures vector quality.

### Metrics

| Metric | Type | Description | Implementation |
|--------|------|-------------|----------------|
| `embedding_dimensions` | int | Actual embedding dimensions | `len(vectors[0])` |
| `avg_vector_norm` | float | Average L2 norm | `mean(norm(v) for v in vectors)` |
| `norm_stdev` | float | Std dev of norms | `stdev(list_of_norms)` |
| `avg_cosine_similarity` | float | Mean pairwise similarity among all chunks | sample-based to avoid O(n²) |
| `dimension_utilization` | % | % of dims with non-zero variance | `count(std > 0.01) / dims * 100` |
| `zero_vector_rate` | % | % of chunks that got zero-vector (failure) | already recorded in litellm_embedding |
| `model_used` | str | Which embedding model was used | from config |
| `embedding_time_avg` | ms | Avg time per batch | `total_time / batch_count` |

### Where to Implement

**New file**: `rag-ingestion-manager/evaluation/embedding_metrics.py`

---

<a name="layer-4"></a>
## 6. Layer 4: Pipeline Throughput & Reliability

Run per sync cycle — measures overall pipeline health.

### Metrics

| Metric | Type | Source |
|--------|------|--------|
| `total_files_processed` | int | sync result `added + updated + unchanged` |
| `files_added` | int | sync result `added` |
| `files_updated` | int | sync result `updated` |
| `files_deleted` | int | sync result `deleted` |
| `total_documents` | int | `doc_count` after sync |
| `total_chunks` | int | `chunk_count` after sync |
| `total_errors` | int | `len(errors)` |
| `sync_duration_ms` | ms | wall clock of sync |
| `docs_per_second` | float | `doc_count / duration_sec` |
| `chunks_per_doc` | float | chunks / documents ratio |
| `points_in_qdrant` | int | Qdrant collection points_count |
| `qdrant_vs_indexed_mismatch` | % | `abs(qdrant_points - total_chunks) / max_value * 100` |

### Where to Implement

**New file**: `rag-ingestion-manager/evaluation/pipeline_health.py`

### Cross-Validation (Critical)
Compare `total_chunks` from application DB against Qdrant's `points_count`. A mismatch means stale/desynced data — the bug we just fixed should be caught here.

```python
def cross_validate(qdrant_client, collection_name: str, db_chunk_count: int) -> dict:
    qdrant_points = qdrant_client.get_collection(collection_name).points_count
    return {
        "qdrant_points": qdrant_points,
        "db_chunk_count": db_chunk_count,
        "in_sync": qdrant_points == db_chunk_count,
        "mismatch": abs(qdrant_points - db_chunk_count),
    }
```

---

<a name="layer-5"></a>
## 7. Layer 5: End-to-End Retrieval via RAGAS/DeepEval

This is the **most important layer** — does the ingested data actually produce good search results?

### Frameworks Evaluated

| Framework | Stars | Strengths | Works with LiteLLM |
|-----------|-------|-----------|--------------------|
| **RAGAS** | 14.5k | Mature, LLM-as-judge metrics, synthetic test data generation, active community | Yes (bring your own LLM) |
| **DeepEval** | 16.4k | Pytest-native, 50+ metrics, CI/CD integration, JSON-confinable LLM judge, synthetic data generation | Yes (any OpenAI-compatible endpoint = LiteLLM) |

**Recommendation: Use RAGAS directly** (lighter weight, purpose-built for RAG metrics). If we need deeper CI/CD integration later, we can add DeepEval.

### Metrics (from RAGAS)

| Metric | What it measures | Why it matters for ingestion |
|--------|-----------------|------------------------------|
| **Context Precision** | Signal-to-noise ratio in retrieved chunks | Bad chunking → noisy context → low precision |
| **Context Recall** | % of relevant info retrieved | Bad extraction → missing info → low recall |
| **Faithfulness** | % of generated statements supported by context | Hallucinations increase when chunks lose context |
| **Answer Relevancy** | Is the actual answer relevant to the question | Chunk spillover / missing context |
| **Noise Sensitivity** | How much noise degrades performance | Poor chunking boundaries |

### Required Data

RAGAS needs **test datasets** with:
- `question` — A query
- `answer` — The pipeline's generated response (using LiteLLM)
- `contexts` — List of retrieved chunks from Qdrant
- `ground_truth` — The ideal/expected answer

### How to Create Test Datasets

**Option A: Manual** — Create 20-50 hand-curated QA pairs with expected contexts and answers. Gold standard but time-consuming.

**Option B: Synthetic (RAGAS)** — Use RAGAS's `TestDataGenerator` to:
1. Feed source documents to the generator
2. It creates Q/A/context triples using an LLM
3. Result: A `Dataset` object ready for evaluation

**Option C: Hybrid** — Start with 5-10 manual golden questions, then expand via synthetic generation.

### Implementation

**New file**: `rag-ingestion-manager/evaluation/retrieval_eval.py`

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    noise_sensitivity,
)
from datasets import Dataset

def evaluate_retrieval(
    collection_name: str,
    test_questions: list[str],
    ground_truths: list[str],
    llm_client,
    embedding_model: str,
) -> dict:
    """
    1. For each question, retrieve top-k chunks from Qdrant
    2. Generate answer using LiteLLM chat model
    3. Run RAGAS metrics
    4. Return scores
    """
    # Build dataset
    data = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }
    
    for q, gt in zip(test_questions, ground_truths):
        # Search Qdrant for relevant chunks
        results = search_qdrant(collection_name, q, embedding_model)
        contexts = [r.payload["content"] for r in results]
        
        # Generate answer
        answer = generate_answer(q, contexts, llm_client)
        
        data["question"].append(q)
        data["answer"].append(answer)
        data["contexts"].append(contexts)
        data["ground_truth"].append(gt)
    
    dataset = Dataset.from_dict(data)
    
    # Evaluate
    result = evaluate(
        dataset,
        metrics=[
            context_precision,
            context_recall,
            faithfulness,
            answer_relevancy,
            noise_sensitivity,
        ],
    )
    
    return result
```

---

<a name="architecture"></a>
## 8. Architecture & Files

### New Files

| File | Purpose |
|------|---------|
| `rag-ingestion-manager/evaluation/__init__.py` | Package init |
| `rag-ingestion-manager/evaluation/extraction_metrics.py` | Layer 1 |
| `rag-ingestion-manager/evaluation/chunking_metrics.py` | Layer 2 |
| `rag-ingestion-manager/evaluation/embedding_metrics.py` | Layer 3 |
| `rag-ingestion-manager/evaluation/pipeline_health.py` | Layer 4 (including cross-validation) |
| `rag-ingestion-manager/evaluation/retrieval_eval.py` | Layer 5 (RAGAS) |
| `rag-ingestion-manager/evaluation/runner.py` | Orchestrates all layers |
| `rag-ingestion-manager/evaluation/reporter.py` | Formats and stores results |
| `rag-ingestion-manager/evaluation/test_data.py` | Golden test dataset management |
| `rag-ingestion-manager/api/routes/evaluation.py` | REST endpoint for evaluation |
| `rag-ingestion-manager/api/routes/test_data.py` | REST endpoint for test datasets |
| `rag-ingestion-manager/evaluation/requirements.txt` | Dependencies (ragas, datasets) |
| `tests/evaluation/test_extraction.py` | Unit tests |
| `tests/evaluation/test_chunking.py` | Unit tests |
| `tests/evaluation/test_embedding.py` | Unit tests |
| `tests/evaluation/test_retrieval.py` | Integration tests |

### Modified Files

| File | Change |
|------|--------|
| `rag-ingestion-manager/services/collection_sync_service.py` | Call evaluation runner after sync completes |
| `rag-ingestion-manager/api/main.py` | Register evaluation routes |
| `rag-ingestion-manager/core/db.py` | Add evaluation results table (optional) |
| `rag-ingestion-manager/monitoring/worker.py` | Optionally run evaluation on schedule |
| `rag-ingestion-manager/.env.example` | Add RAGAS/eval env vars |
| `.gitignore` | Add `test_data/`, `eval_reports/` |

### Database Tables (optional — can use file-based store)

```sql
CREATE TABLE evaluation_results (
    id UUID PRIMARY KEY,
    collection_name VARCHAR(255),
    eval_type VARCHAR(50),        -- 'post_sync', 'manual', 'scheduled'
    layer VARCHAR(50),            -- 'extraction', 'chunking', 'embedding', 'pipeline', 'retrieval'
    metrics JSONB,                -- the actual metric values
    passed_checks JSONB,          -- pass/fail per threshold
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE golden_test_questions (
    id UUID PRIMARY KEY,
    collection_name VARCHAR(255),
    question TEXT,
    ground_truth TEXT,
    expected_context_sources JSONB,  -- list of file names / chunk IDs
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);
```

---

<a name="impl-plan"></a>
## 9. Implementation Plan

### Phase 1: Foundation (Tasks 1-3)

#### Task 1: Create evaluation package structure

**Objective:** Set up the evaluation directory, package init, and requirements

**Files:**
- Create: `rag-ingestion-manager/evaluation/__init__.py`
- Create: `rag-ingestion-manager/evaluation/requirements.txt`

**Steps:**
1. Create `__init__.py` with `from .runner import run_evaluation`
2. Create `requirements.txt` with:
   ```
   ragas>=0.2.0
   datasets>=2.14.0
   numpy>=1.24.0
   scipy>=1.10.0
   ```
3. Install deps: `pip install -r requirements.txt`
4. Commit

#### Task 2: Implement Layers 1-4 (quality metrics)

**Objective:** Build the metric calculators for extraction, chunking, embedding, and pipeline health

**Files:**
- Create: `rag-ingestion-manager/evaluation/extraction_metrics.py`
- Create: `rag-ingestion-manager/evaluation/chunking_metrics.py`
- Create: `rag-ingestion-manager/evaluation/embedding_metrics.py`
- Create: `rag-ingestion-manager/evaluation/pipeline_health.py`

**Steps:**
1. Implement `extraction_metrics.py`:
   - `collect_extraction_stats(documents: list[Document], errors: list[str], durations: list[float]) -> dict`
   - Compute: success rate, empty rate, avg length, stdev, format coverage, error rate, avg time

2. Implement `chunking_metrics.py`:
   - `evaluate_chunks(chunks: list[Chunk], config: dict) -> dict`
   - Compute: avg size, stdev, percentiles, chunks per doc, overlap accuracy, duplicate rate

3. Implement `embedding_metrics.py`:
   - `evaluate_embeddings(embeddings: list[EmbeddingVector]) -> dict`
   - Compute: avg norm, norm stdev, avg pairwise cosine similarity (sampled), dimension utilization, zero-vector rate

4. Implement `pipeline_health.py`:
   - `cross_validate_qdrant(qdrant_client, collection_name, db_chunk_count) -> dict`
   - `collect_pipeline_stats(sync_result: dict, duration: float) -> dict`
   - Compute: total files, errors, sync duration, docs_per_sec, qdrant vs indexed comparison

#### Task 3: Build the evaluation runner + reporter

**Objective:** Create the orchestrator that runs all metric layers and stores results

**Files:**
- Create: `rag-ingestion-manager/evaluation/runner.py`
- Create: `rag-ingestion-manager/evaluation/reporter.py`

**Steps:**
1. Create `runner.py`:
   ```python
   def run_evaluation(
       collection_name: str,
       pipeline: IngestionPipeline,
       documents: list[Document],
       chunks: list[Chunk],
       embeddings: list[EmbeddingVector],
       sync_result: dict,
       sync_duration: float,
       db_session,
   ) -> EvaluationResult:
       results = {"collection": collection_name, "layers": {}}
       
       # Layer 1: Extraction
       results["layers"]["extraction"] = collect_extraction_stats(...)
       
       # Layer 2: Chunking
       chunking_config = pipeline.stages_config.get("chunking", {})
       results["layers"]["chunking"] = evaluate_chunks(chunks, chunking_config)
       
       # Layer 3: Embedding
       results["layers"]["embedding"] = evaluate_embeddings(embeddings)
       
       # Layer 4: Pipeline health
       results["layers"]["pipeline"] = collect_pipeline_stats(sync_result, sync_duration)
       # Cross-validate with Qdrant
       qdrant_cv = cross_validate_qdrant(...)
       results["layers"]["pipeline"]["qdrant_validation"] = qdrant_cv
       
       return EvaluationResult(
           collection_name=collection_name,
           metrics=results,
           passed=all(qdrant_cv["in_sync"], ...),
           timestamp=datetime.utcnow(),
       )
   ```

2. Create `reporter.py`:
   - `format_report(result: EvaluationResult) -> str` — human-readable markdown
   - `store_result(result: EvaluationResult, db_session)` — persist to DB or file
   - `compare_baseline(result: EvaluationResult, baseline: str) -> dict` — diff against previous run to detect regressions

### Phase 2: Integration (Tasks 4-6)

#### Task 4: Integrate evaluation into sync cycle

**Objective:** After every sync_collection() call, emit evaluation results

**Files:**
- Modify: `rag-ingestion-manager/services/collection_sync_service.py`

**Changes in `_run_connector_file_ingest`:**
After `pipeline.run_indexing()`, collect documents/chunks/embeddings and call evaluation runner:
```python
# At the end of _run_connector_file_ingest, just before the return:
eval_result = run_evaluation(
    collection_name=knowledge_source_name,
    pipeline=pipeline,
    documents=documents,
    chunks=chunks,
    embeddings=embeddings,
    sync_result={"added": 1, ...},
    sync_duration=time.time() - start_time,
    db_session=db,
)
```

**Changes in `sync_collection`:**
After the per-file loop completes, aggregate per-file eval results into a collection-level report.

#### Task 5: Create CLI command

**Objective:** Add `ingestion-eval` CLI to manually evaluate any collection

**New file:** `rag-ingestion-manager/scripts/eval_cli.py`

```bash
# Usage examples:
python scripts/eval_cli.py --collection my-resume-vecstore
python scripts/eval_cli.py --collection my-resume-vecstore --layers extraction,chunking
python scripts/eval_cli.py --collection my-resume-vecstore --compare-with last
python scripts/eval_cli.py --list-collections
```

**Implementation pattern:**
```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", required=True)
    parser.add_argument("--layers", default="all")
    parser.add_argument("--compare-with", default=None)
    parser.add_argument("--output", choices=["json", "markdown", "table"], default="markdown")
    
    args = parser.parse_args()
    result = run_evaluation_for_collection(args.collection, args.layers.split(","))
    print(format_report(result, args.output))
```

#### Task 6: Add REST API endpoints

**Objective:** Enable on-demand evaluation via API (for UI integration)

**New file:** `rag-ingestion-manager/api/routes/evaluation.py`

**Endpoints:**
- `POST /api/v1/collections/{name}/evaluate` — Run evaluation on a collection
- `GET /api/v1/collections/{name}/evaluations` — List historical evaluation results
- `GET /api/v1/collections/{name}/evaluations/{eval_id}` — Get specific result
- `GET /api/v1/collections/{name}/evaluations/latest` — Get most recent result
- `GET /api/v1/evaluations/test-data` — List/manage golden test questions

### Phase 3: Advanced RAGAS Integration (Tasks 7-9)

#### Task 7: Create golden test dataset management

**Objective:** Build the test dataset CRUD for RAGAS evaluation

**Files:**
- Create: `rag-ingestion-manager/evaluation/test_data.py`
- Create: `rag-ingestion-manager/api/routes/test_data.py`

**Implementation:**
```python
class GoldenTestSet:
    """Manages QA pairs for evaluating retrieval quality."""
    
    @staticmethod
    def load(collection_name: str) -> list[TestQuestion]:
        """Load from file or DB."""
        ...
    
    @staticmethod
    def from_collection_documents(collection_name: str, llm_client, count: int = 20) -> list[TestQuestion]:
        """Use RAGAS TestDataGenerator to create synthetic questions from ingested docs."""
        ...
    
    @staticmethod
    def add(question: str, ground_truth: str, expected_sources: list[str], collection_name: str):
        """Add a hand-curated golden question."""
        ...
```

#### Task 8: Implement RAGAS evaluation

**Objective:** Wire up RAGAS metrics against Qdrant retrieval + LiteLLM generation

**Files:**
- Modify: `rag-ingestion-manager/evaluation/retrieval_eval.py`
- Create: `rag-ingestion-manager/evaluation/retrieval_config.yaml` (optional)

**Implementation:**

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness, answer_relevancy, context_precision, context_recall
)
from datasets import Dataset
from qdrant_client import QdrantClient

def evaluate_retrieval(
    collection_name: str,
    test_questions: list[dict],  # [{question, ground_truth, expected_contexts?}]
    qdrant_client: QdrantClient,
    llm_client,  # LiteLLM OpenAI-compatible client
    chat_model: str = "llama-3.3-70b-versatile",
    embed_model: str = "nvidia-embed",
    top_k: int = 5,
) -> dict:
    """
    1. For each golden question, retrieve top-k from Qdrant
    2. Generate answer via LiteLLM chat
    3. Evaluate with RAGAS
    """
    data = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
    
    for q in test_questions:
        # Embed query
        query_vector = llm_client.embeddings.create(
            model=embed_model, input=[q["question"]],
            extra_body={"input_type": "query", "encoding_format": "float"}
        ).data[0].embedding
        
        # Search Qdrant
        search_result = qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
        )
        contexts = [hit.payload.get("content", "") for hit in search_result]
        
        # Generate answer
        response = llm_client.chat.completions.create(
            model=chat_model,
            messages=[
                {"role": "system", "content": "Answer based ONLY on the provided context."},
                {"role": "user", "content": f"Context:\n{chr(10).join(contexts)}\n\nQuestion: {q['question']}"}
            ],
        )
        answer = response.choices[0].message.content
        
        data["question"].append(q["question"])
        data["answer"].append(answer)
        data["contexts"].append(contexts)
        data["ground_truth"].append(q["ground_truth"])
    
    # Run RAGAS
    dataset = Dataset.from_dict(data)
    result = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision, context_recall])
    
    return {
        "ragas_scores": {k: float(v) for k, v in result.items()},
        "num_questions": len(test_questions),
        "top_k": top_k,
        "embed_model": embed_model,
        "chat_model": chat_model,
        "timestamp": datetime.utcnow().isoformat(),
    }
```

#### Task 9: Wire RAGAS into runner + scheduled eval

**Objective:** Make Layer 5 runnable from the evaluation runner

**Files:**
- Modify: `rag-ingestion-manager/evaluation/runner.py`
- Modify: `rag-ingestion-manager/evaluation/reporter.py`

### Phase 4: Alerting & Dashboard (Tasks 10-11)

#### Task 10: Thresholds & Regression Detection

**Objective:** Define pass/fail thresholds per metric, detect drift

**New file:** `rag-ingestion-manager/evaluation/thresholds.yaml`

```yaml
# Evaluation thresholds per layer
extraction:
  success_rate: { min: 0.95 }
  empty_extraction_rate: { max: 0.05 }
  
chunking:
  avg_chunk_size: { min: 100, max: 2000 }
  empty_chunks: { max: 0 }
  duplicate_content_rate: { max: 0.01 }
  
embedding:
  zero_vector_rate: { max: 0.05 }
  dimension_utilization: { min: 0.5 }
  
pipeline:
  qdrant_mismatch: { max: 0 }
  error_rate: { max: 0.05 }
  
retrieval:
  faithfulness: { min: 0.7 }
  context_precision: { min: 0.6 }
  context_recall: { min: 0.6 }
  answer_relevancy: { min: 0.7 }
```

#### Task 11: Scheduled evaluation via cron job

**Objective:** Run evaluation on a schedule (hourly/daily) + alert on regression

**New cron job:**
- Schedule: `0 */6 * * *` (every 6 hours)
- Runs `evaluate_all_monitored_collections()`
- Compares against baseline from previous run
- Reports pass/fail or regression in Discord

---

<a name="verification"></a>
## 10. Verification & Testing

### Unit Tests

| Test | What it verifies | File |
|------|-----------------|------|
| `test_extraction_metrics_basic` | Statistics computed correctly for valid input | `tests/evaluation/test_extraction.py` |
| `test_extraction_metrics_empty` | Handles empty document list gracefully | same |
| `test_chunking_metrics_size_distribution` | Percentiles computed correctly | `tests/evaluation/test_chunking.py` |
| `test_chunking_metrics_overlap` | Overlap accuracy measured correctly | same |
| `test_embedding_metrics_similarity` | Cosine similarity on known vectors | `tests/evaluation/test_embedding.py` |
| `test_cross_validate_qdrant` | Detects mismatched counts | `tests/evaluation/test_pipeline_health.py` |

### Integration Tests

| Test | What it verifies |
|------|-----------------|
| `test_eval_runner_full` | Full eval run on a small test collection produces all metric layers |
| `test_ragas_with_litellm` | RAGAS evaluation works end-to-end with LiteLLM proxy |
| `test_eval_cli` | CLI command produces output for a real collection |
| `test_eval_api` | API endpoint returns 200 with valid metrics |

### Manual Verification Steps

1. Create a small test collection with 2-3 PDFs
2. Run `python scripts/eval_cli.py --collection test-coll`
3. Verify all 4 layers (1-4) produce non-null metrics
4. Add 5 golden questions
5. Run `python scripts/eval_cli.py --collection test-coll --layers retrieval`
6. Verify RAGAS scores between 0 and 1
7. Delete a file from GDrive → sync → re-run eval → verify qdrant_mismatch is 0

---

## Open Questions

| Question | Decision Needed By |
|----------|-------------------|
| File-based or DB-based evaluation result storage? | Phase 1 |
| Use RAGAS directly or through DeepEval? | **Recommended: RAGAS** (lighter) |
| Share a single judge LLM or use the collection's configured model? | Collection model (keeps settings consistent) |
| Add evaluation UI to frontend or keep as CLI only? | CLI first, API second, UI optional |
| How many golden questions minimum for meaningful RAGAS scores? | 10+ manual, 50+ synthetic |
| Should we run eval inline (on every sync) or async (separate process)? | Inline for layers 1-4, async for layer 5 (expensive) |

---

## Dependencies to Install

```bash
# Core
pip install ragas>=0.2.0 datasets>=2.14.0

# Already installed:
# kreuzberg, qdrant-client, openai, sqlalchemy, numpy

# For evaluation
pip install pyyaml>=6.0 matplotlib>=3.7.0  # optional, for charting
```
