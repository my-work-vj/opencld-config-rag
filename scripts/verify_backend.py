"""Smoke-test both RAG backend services — run while :8081 and :8082 are up."""

from __future__ import annotations

import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

INGESTION = "http://localhost:8081/api/v1"
QUERY = "http://localhost:8082/api/v1"
TIMEOUT = 120.0
EXPECTED_PIPELINES = {"default_rag", "naive_rag", "vector_rag", "hybrid_rag"}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    elapsed_ms: float = 0


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "", elapsed_ms: float = 0) -> None:
        self.checks.append(Check(name, ok, detail, elapsed_ms))

    def failed(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]


def _get(client: httpx.Client, base: str, path: str, name: str, report: Report) -> Any | None:
    t0 = time.perf_counter()
    try:
        r = client.get(f"{base}{path}", timeout=TIMEOUT)
        elapsed = (time.perf_counter() - t0) * 1000
        if r.status_code >= 400:
            report.add(name, False, f"HTTP {r.status_code}: {r.text[:300]}", elapsed)
            return None
        report.add(name, True, f"HTTP {r.status_code}", elapsed)
        return r.json()
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        report.add(name, False, str(e), elapsed)
        return None


def _post(client: httpx.Client, base: str, path: str, body: dict, name: str, report: Report) -> Any | None:
    t0 = time.perf_counter()
    try:
        r = client.post(f"{base}{path}", json=body, timeout=TIMEOUT)
        elapsed = (time.perf_counter() - t0) * 1000
        if r.status_code >= 400:
            report.add(name, False, f"HTTP {r.status_code}: {r.text[:500]}", elapsed)
            return None
        report.add(name, True, f"HTTP {r.status_code}", elapsed)
        return r.json()
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        report.add(name, False, str(e), elapsed)
        return None


def main() -> int:
    report = Report()
    marker = f"OPNCLD_VERIFY_{uuid.uuid4().hex[:8]}"

    with httpx.Client() as client:
        # --- Health ---
        for label, base in [("ingestion", INGESTION), ("query", QUERY)]:
            data = _get(client, base, "/health", f"{label} GET /health", report)
            if data:
                healthy = data.get("status") == "healthy"
                deps = all([
                    data.get("llm_available"),
                    data.get("qdrant_available"),
                    data.get("postgres_available"),
                ])
                report.add(
                    f"{label} dependencies",
                    healthy and deps,
                    json.dumps({
                        "status": data.get("status"),
                        "llm": data.get("llm_available"),
                        "qdrant": data.get("qdrant_available"),
                        "postgres": data.get("postgres_available"),
                        "pipelines": data.get("pipeline_count"),
                    }),
                )

        # --- Strategies & collections ---
        for label, base in [("ingestion", INGESTION), ("query", QUERY)]:
            strat = _get(client, base, "/strategies", f"{label} GET /strategies", report)
            if strat:
                report.add(
                    f"{label} strategies non-empty",
                    bool(strat),
                    f"stages: {list(strat.keys())}",
                )
            cols = _get(client, base, "/collections", f"{label} GET /collections", report)
            if cols:
                names = [c.get("name") for c in cols]
                report.add(
                    f"{label} rag_documents collection",
                    "rag_documents" in names,
                    f"collections: {names}",
                )

        # --- Pipeline CRUD (read-only + resolved) ---
        for label, base in [("ingestion", INGESTION), ("query", QUERY)]:
            plist = _get(client, base, "/pipelines", f"{label} GET /pipelines", report)
            if plist:
                ids = {p["id"] for p in plist.get("pipelines", [])}
                missing = EXPECTED_PIPELINES - ids
                report.add(
                    f"{label} expected pipelines",
                    not missing,
                    f"missing={missing}" if missing else f"count={len(ids)}",
                )

        pid = "default_rag"
        _get(client, INGESTION, f"/pipelines/{pid}", "ingestion GET /pipelines/{id}", report)
        _get(client, QUERY, f"/pipelines/{pid}", "query GET /pipelines/{id}", report)
        _get(client, INGESTION, f"/pipelines/{pid}/resolved/ingestion", "ingestion resolved config", report)
        _get(client, QUERY, f"/pipelines/{pid}/resolved/query", "query resolved config", report)

        # --- Ingest (raw text with unique marker) ---
        test_text = (
            f"Verification document {marker}. "
            "The secret project codename is AURORA-NEXUS. "
            "This text is used only for automated backend smoke testing."
        )
        ingest_body = {
            "source": test_text,
            "source_type": "text",
            "pipeline": "default_rag",
        }
        ingest_result = _post(
            client, INGESTION, "/ingest", ingest_body,
            "ingestion POST /ingest", report,
        )
        if ingest_result:
            ok = (
                ingest_result.get("status") == "success"
                and ingest_result.get("chunk_count", 0) > 0
                and ingest_result.get("embedding_count", 0) > 0
            )
            report.add(
                "ingest produced chunks+embeddings",
                ok,
                json.dumps({
                    "chunks": ingest_result.get("chunk_count"),
                    "embeddings": ingest_result.get("embedding_count"),
                    "collection": ingest_result.get("collection_name"),
                }),
            )

        # Brief pause for Qdrant indexing visibility
        time.sleep(2)

        # --- Query ---
        query_body = {
            "query": f"What is the secret project codename mentioned in {marker}?",
            "pipeline": "default_rag",
            "top_k": 3,
        }
        query_result = _post(
            client, QUERY, "/query", query_body,
            "query POST /query (default_rag)", report,
        )
        if query_result:
            has_chunks = len(query_result.get("chunks", [])) > 0
            has_response = bool(query_result.get("response"))
            mentions_marker = marker in str(query_result.get("chunks", [])) or "AURORA" in query_result.get("response", "").upper()
            report.add(
                "query returned chunks",
                has_chunks,
                f"chunk_count={len(query_result.get('chunks', []))}",
            )
            report.add(
                "query returned LLM response",
                has_response,
                (query_result.get("response") or "")[:120],
            )
            report.add(
                "query found ingested content (marker or codename)",
                mentions_marker,
                "marker/codename in chunks or response",
            )

        # --- Compare ---
        compare_body = {
            "query": "What is AURORA-NEXUS?",
            "pipelines": ["naive_rag", "vector_rag"],
            "top_k": 3,
        }
        compare_result = _post(
            client, QUERY, "/compare", compare_body,
            "query POST /compare", report,
        )
        if compare_result:
            results = compare_result.get("results", [])
            errors = [r for r in results if r.get("retrieval_method") == "error"]
            report.add(
                "compare all pipelines succeeded",
                len(results) == 2 and not errors,
                f"errors={[r.get('pipeline') for r in errors]}" if errors else "ok",
            )

        # --- Logs ---
        logs = _get(client, QUERY, "/logs?limit=5", "query GET /logs", report)
        if logs is not None:
            report.add("logs endpoint returns list", isinstance(logs, list), f"count={len(logs)}")

        # --- Knowledge Source / Base / Agent ---
        ks_name_a = f"verify-ks-a-{marker}"
        ks_name_b = f"verify-ks-b-{marker}"
        kb_name = f"verify-kb-{marker}"
        agent_kb_name = f"verify-agent-kb-{marker}"
        agent_ks_name = f"verify-agent-ks-{marker}"

        ks_list = _get(client, INGESTION, "/knowledge-sources", "GET /knowledge-sources", report)

        ks_body_a = {
            "name": ks_name_a,
            "description": "verify source A",
            "pipeline": "default_rag",
        }
        ks_created_a = _post(
            client, INGESTION, "/knowledge-sources", ks_body_a,
            "POST /knowledge-sources (A)", report,
        )
        ks_body_b = {
            "name": ks_name_b,
            "description": "verify source B",
            "pipeline": "naive_rag",
        }
        ks_created_b = _post(
            client, INGESTION, "/knowledge-sources", ks_body_b,
            "POST /knowledge-sources (B)", report,
        )

        test_text_a = f"Source A marker {marker} codename ALPHA-{marker}"
        test_text_b = f"Source B marker {marker} codename BRAVO-{marker}"

        if ks_created_a:
            ingest_a = _post(
                client,
                INGESTION,
                f"/knowledge-sources/{ks_name_a}/ingest",
                {"source": test_text_a, "source_type": "text"},
                "POST /knowledge-sources/{name}/ingest (A)",
                report,
            )
            if ingest_a:
                report.add(
                    "KS ingest A success",
                    ingest_a.get("status") == "success",
                    json.dumps({"chunks": ingest_a.get("chunk_count")}),
                )

        if ks_created_b:
            ingest_b = _post(
                client,
                INGESTION,
                f"/knowledge-sources/{ks_name_b}/ingest",
                {"source": test_text_b, "source_type": "text"},
                "POST /knowledge-sources/{name}/ingest (B)",
                report,
            )
            if ingest_b:
                report.add(
                    "KS ingest B success",
                    ingest_b.get("status") == "success",
                    json.dumps({"chunks": ingest_b.get("chunk_count")}),
                )

        time.sleep(2)

        # --- Prompt templates ---
        prompt_id = f"verify-prompt-{marker}"
        prompt_body = {
            "id": prompt_id,
            "name": "Verify Prompt",
            "description": "verify",
            "system_prompt": "You are a test assistant. Answer briefly.",
        }
        _post(client, QUERY, "/prompt-templates", prompt_body, "POST /prompt-templates", report)
        _get(client, QUERY, f"/prompt-templates/{prompt_id}", "GET /prompt-templates/{id}", report)
        _post(
            client, QUERY, f"/prompt-templates/{prompt_id}/versions",
            {"system_prompt": "You are a test assistant v2.", "changelog": "v2"},
            "POST /prompt-templates/{id}/versions", report,
        )
        try:
            r = client.post(f"{QUERY}/prompt-templates/seed?dry_run=true", timeout=30)
            report.add("prompt seed dry_run", r.status_code < 400, r.text[:200])
        except Exception as e:
            report.add("prompt seed dry_run", False, str(e))

        kb_body = {
            "name": kb_name,
            "description": "verify KB",
            "source_names": [ks_name_a, ks_name_b],
        }
        kb_created = _post(
            client, QUERY, "/knowledge-bases", kb_body,
            "POST /knowledge-bases", report,
        )

        agent_kb_body = {
            "name": agent_kb_name,
            "description": "KB agent",
            "knowledge_base_names": [kb_name],
            "prompt_template_id": prompt_id,
            "retrieval_strategy": "multi_collection",
            "reranking_strategy": "pass_through",
            "top_k": 3,
        }
        if kb_created:
            _post(
                client, QUERY, "/agents", agent_kb_body,
                "POST /agents (KB)", report,
            )
            agent_q = _post(
                client,
                QUERY,
                f"/agents/{agent_kb_name}/query",
                {"query": f"What codename is in source B with marker {marker}?"},
                "POST /agents/{name}/query (KB)",
                report,
            )
            if agent_q:
                mentions = "BRAVO" in agent_q.get("response", "").upper() or marker in str(agent_q.get("chunks", []))
                report.add(
                    "KB agent query returned merged results",
                    len(agent_q.get("sources_searched", [])) >= 2 and bool(agent_q.get("response")),
                    f"sources={agent_q.get('sources_searched')}",
                )
                report.add("KB agent found ingested content", mentions, "marker/codename check")

        agent_ks_body = {
            "name": agent_ks_name,
            "description": "single source agent",
            "knowledge_source_name": ks_name_a,
            "retrieval_strategy": "naive_rag",
            "reranking_strategy": "pass_through",
            "top_k": 3,
        }
        if ks_created_a:
            _post(
                client, QUERY, "/agents", agent_ks_body,
                "POST /agents (KS)", report,
            )
            agent_ks_q = _post(
                client,
                QUERY,
                f"/agents/{agent_ks_name}/query",
                {"query": f"What codename is in source A with marker {marker}?"},
                "POST /agents/{name}/query (KS)",
                report,
            )
            if agent_ks_q:
                report.add(
                    "KS agent query succeeded",
                    bool(agent_ks_q.get("response")),
                    agent_ks_q.get("response", "")[:120],
                )

        health_i = _get(client, INGESTION, "/health", "ingestion health counts", report)
        if health_i:
            report.add(
                "ingestion health has KS count",
                "knowledge_source_count" in health_i,
                json.dumps({
                    "ks": health_i.get("knowledge_source_count"),
                }),
            )
        health_q = _get(client, QUERY, "/health", "query health counts", report)
        if health_q:
            report.add(
                "query health has entity counts",
                all(k in health_q for k in ("knowledge_source_count", "knowledge_base_count", "agent_count")),
                json.dumps({
                    "ks": health_q.get("knowledge_source_count"),
                    "kb": health_q.get("knowledge_base_count"),
                    "agents": health_q.get("agent_count"),
                }),
            )

        try:
            r = client.post(f"{QUERY}/agents/seed?dry_run=true", timeout=30)
            report.add("agent pipeline seed dry_run", r.status_code < 400, r.text[:200])
        except Exception as e:
            report.add("agent pipeline seed dry_run", False, str(e))

        # --- Seed dry-run (no DB mutation) ---
        t0 = time.perf_counter()
        try:
            r = client.post(f"{INGESTION}/pipelines/seed?dry_run=true", timeout=30)
            elapsed = (time.perf_counter() - t0) * 1000
            if r.status_code >= 400:
                report.add("seed dry_run", False, f"HTTP {r.status_code}: {r.text[:200]}", elapsed)
            else:
                data = r.json()
                report.add(
                    "seed dry_run",
                    data.get("dry_run") is True and data.get("count", 0) >= 4,
                    json.dumps(data),
                    elapsed,
                )
        except Exception as e:
            report.add("seed dry_run", False, str(e))

    # --- Print report ---
    print("\n=== Backend Verification Report ===\n")
    for c in report.checks:
        icon = "PASS" if c.ok else "FAIL"
        ms = f" ({c.elapsed_ms:.0f}ms)" if c.elapsed_ms else ""
        print(f"[{icon}] {c.name}{ms}")
        if c.detail:
            print(f"       {c.detail}")

    failed = report.failed()
    print(f"\nTotal: {len(report.checks)} checks, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
