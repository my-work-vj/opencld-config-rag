#!/usr/bin/env python3
"""
CLI to evaluate a collection's ingestion pipeline (Layers 1-5).

Usage:
    python scripts/eval_cli.py --collection my-collection                          # Layers 1-4
    python scripts/eval_cli.py --collection my-collection --run-retrieval          # Full eval (1-5)
    python scripts/eval_cli.py --list-collections                                  # Browse
    python scripts/eval_cli.py --collection my-col --add-question "Q?" "A?"        # Add test question
    python scripts/eval_cli.py --collection my-col --list-questions                # Show test data
    python scripts/eval_cli.py --collection my-col --generate-synthetic 5          # Auto-generate Qs
    python scripts/eval_cli.py --collection my-col --compare                       # Compare vs baseline
"""

import argparse
import json
import os
import sys
from datetime import datetime

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_script_dir, ".."))
_pkg_root = os.path.join(_project_root, "rag-ingestion-manager")
sys.path.insert(0, _pkg_root)
sys.path.insert(0, _project_root)


def list_collections():
    """List all knowledge sources from the DB."""
    from rag_shared.db import SessionLocal as SharedSession
    from rag_shared.knowledge_repo import KnowledgeSourceRepo

    db = SharedSession()
    try:
        records = KnowledgeSourceRepo.list_all(db)
        print(f"\n{'Name':<35} {'Docs':>5} {'Chunks':>7} {'Status':<12} {'Vector Size':<12}")
        print(f"{'-'*35} {'-'*5} {'-'*7} {'-'*12} {'-'*12}")
        for r in records:
            print(f"{r.name:<35} {r.document_count or 0:>5} {r.chunk_count or 0:>7} {r.status or 'unknown':<12} {r.vector_size or '-':<12}")
        return records
    finally:
        db.close()


def add_question(collection_name: str, question: str, answer: str):
    """Add a golden test question."""
    from evaluation.test_data import GoldenTestSet
    ts = GoldenTestSet(collection_name)
    ts.add(question=question, ground_truth=answer)
    print(f"  Added question to {collection_name}: {question[:60]}...")


def list_questions(collection_name: str):
    """List golden test questions for a collection."""
    from evaluation.test_data import GoldenTestSet
    ts = GoldenTestSet(collection_name)
    questions = ts.list_all()
    if not questions:
        print(f"  No test questions for collection '{collection_name}'.")
        print(f"  Add one: python scripts/eval_cli.py --collection \"{collection_name}\" --add-question \"Q\" \"A\"")
        return
    print(f"\n  Golden Test Questions for `{collection_name}`:\n")
    for i, q in enumerate(questions, 1):
        print(f"  [{i}] {q['question'][:80]}")
        print(f"       Answer: {q['ground_truth'][:100]}")
        print(f"       ID: {q['question_id'][:12]}...")
        print()


def generate_synthetic(collection_name: str, count: int = 5):
    """Generate synthetic test questions from indexed documents."""
    from evaluation.test_data import GoldenTestSet
    from rag_shared.db import SessionLocal as SharedSession
    from rag_shared.indexed_document_repo import IndexedDocumentRepo
    from openai import OpenAI
    import os as _os

    # Load source texts from indexed documents
    session = SharedSession()
    try:
        records = IndexedDocumentRepo.list_for_collection(session, collection_name)
    finally:
        session.close()

    if not records:
        print("  No indexed documents found for this collection.")
        return

    texts = [
        getattr(r, "content_preview", "") or ""
        for r in records[:10]  # First 10 docs
        if getattr(r, "content_preview", None)
    ]
    if not texts:
        print("  Indexed documents have no content_preview. Run a sync first.")
        return

    print(f"  Generating {count} synthetic questions from {len(texts)} documents...")
    client = OpenAI(
        base_url=_os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1"),
        api_key=_os.getenv("LITELLM_API_KEY", "sk-vj"),
    )
    ts = GoldenTestSet.generate_synthetic(
        collection_name=collection_name,
        source_texts=texts,
        llm_client=client,
        count=count,
    )
    print(f"  Created {ts.count()} new synthetic questions in {collection_name}")


def evaluate_collection(
    collection_name: str,
    output: str = "markdown",
    run_retrieval: bool = False,
    compare: bool = False,
):
    """
    Evaluate a collection by triggering a sync and running metrics.
    """
    import time
    from services.collection_sync_service import sync_collection
    from evaluation.reporter import store_result, format_summary, compare_baseline

    print(f"🚀 Evaluating collection: {collection_name}")
    t0 = time.time()

    try:
        result = sync_collection(collection_name)
        duration = time.time() - t0
    except Exception as exc:
        print(f" Sync failed: {exc}")
        return

    status = result.get("status", "unknown")
    print(f"   Sync completed in {duration:.2f}s — Status: {status}")

    # Run retrieval evaluation if requested
    if run_retrieval and result.get("errors", []):
        print("  Skipping retrieval eval — sync had errors")

    retrieval_run = False
    if run_retrieval:
        from evaluation.test_data import GoldenTestSet
        from evaluation.retrieval_eval import evaluate_retrieval
        from qdrant_client import QdrantClient

        ts = GoldenTestSet(collection_name)
        questions = ts.get_questions()
        if not questions:
            print(f"  No test questions for '{collection_name}'. Skipping retrieval eval.")
            print(f"  Add with: scripts/eval_cli.py --collection \"{collection_name}\" --add-question \"Q\" \"A\"")
        else:
            print(f"  Running retrieval eval with {len(questions)} questions...")

            qclient = QdrantClient(
                host=os.getenv("QDRANT_HOST", "localhost"),
                port=int(os.getenv("QDRANT_PORT", "6333")),
            )
            ret_result = evaluate_retrieval(
                collection_name=collection_name,
                test_questions=[{"question": q.question, "ground_truth": q.ground_truth} for q in questions],
                qdrant_client=qclient,
            )
            # Embed into the layers output
            result["retrieval_result"] = ret_result
            retrieval_run = True

    # Store and format
    report_path = store_result(result)

    if output == "json":
        safe = {k: v for k, v in result.items() if k not in ("evaluation", "retrieval_result")}
        print(f"\n{json.dumps(safe, indent=2, default=str)}")
    elif output == "markdown":
        summary = format_summary({
            "collection_name": collection_name,
            "timestamp": t0,
            "layers": {
                "extraction": result.get("evaluation", {}).get("layers", {}).get("extraction", {}),
                "chunking": result.get("evaluation", {}).get("layers", {}).get("chunking", {}),
                "embedding": result.get("evaluation", {}).get("layers", {}).get("embedding", {}),
                "pipeline": result,
                "retrieval": result.get("retrieval_result"),
            },
        })
        print(f"\n{summary}")
        print(f"  Report saved to: {report_path}")

    # Compare against baseline
    if compare:
        comparison = compare_baseline(
            {
                "collection_name": collection_name,
                "timestamp": t0,
                "layers": {
                    "extraction": result.get("evaluation", {}).get("layers", {}).get("extraction", {}),
                    "chunking": result.get("evaluation", {}).get("layers", {}).get("chunking", {}),
                    "embedding": result.get("evaluation", {}).get("layers", {}).get("embedding", {}),
                    "pipeline": result,
                    "retrieval": result.get("retrieval_result"),
                },
            }
        )
        if comparison.get("status") == "no_baseline":
            print("  No baseline to compare against (this run is the baseline).")
        elif comparison.get("regressions", []):
            print(f"\n  Regressions ({comparison.get('regression_count', 0)}):")
            for r in comparison["regressions"]:
                print(f"    {r}")
        else:
            print("  No regressions detected.")

    print(f"\n  Report saved: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate a collection's ingestion pipeline (all 5 layers).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python scripts/eval_cli.py --collection my-resume-vecstore
  python scripts/eval_cli.py --collection my-resume-vecstore --run-retrieval
  python scripts/eval_cli.py --collection my-resume-vecstore --add-question "What's in it?" "My resume data"
  python scripts/eval_cli.py --collection my-resume-vecstore --generate-synthetic 5
  python scripts/eval_cli.py --collection my-resume-vecstore --compare
  python scripts/eval_cli.py --list-collections""",
    )
    parser.add_argument("--collection", type=str, help="Collection name to evaluate")
    parser.add_argument("--output", type=str, choices=["markdown", "json", "raw"], default="markdown")
    parser.add_argument("--list-collections", action="store_true", help="List available collections")

    # Test question management
    parser.add_argument("--add-question", nargs=2, metavar=("QUESTION", "ANSWER"), help="Add a golden test question")
    parser.add_argument("--list-questions", action="store_true", help="List golden test questions")
    parser.add_argument("--generate-synthetic", type=int, metavar="N", help="Generate N synthetic test questions")

    # Evaluation options
    parser.add_argument("--run-retrieval", action="store_true", help="Run Layer 5 retrieval evaluation (requires test questions)")
    parser.add_argument("--compare", action="store_true", help="Compare against baseline")

    args = parser.parse_args()

    # Mode: list collections
    if args.list_collections:
        list_collections()
        return

    # Collection is required for all other modes
    if not args.collection:
        print("Error: --collection is required")
        parser.print_help()
        sys.exit(1)

    # Mode: add question
    if args.add_question:
        add_question(args.collection, args.add_question[0], args.add_question[1])
        return

    # Mode: list questions
    if args.list_questions:
        list_questions(args.collection)
        return

    # Mode: generate synthetic
    if args.generate_synthetic:
        generate_synthetic(args.collection, args.generate_synthetic)
        return

    # Mode: evaluate
    evaluate_collection(
        collection_name=args.collection,
        output=args.output,
        run_retrieval=args.run_retrieval,
        compare=args.compare,
    )


if __name__ == "__main__":
    main()
