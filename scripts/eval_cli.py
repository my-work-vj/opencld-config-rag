#!/usr/bin/env python3
"""
CLI to evaluate a collection's ingestion pipeline.

Usage:
    python scripts/eval_cli.py --collection my-collection
    python scripts/eval_cli.py --collection my-collection --output json
    python scripts/eval_cli.py --list-collections
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Ensure the package root is on sys.path
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_script_dir, ".."))
_pkg_root = os.path.join(_project_root, "rag-ingestion-manager")
sys.path.insert(0, _pkg_root)
sys.path.insert(0, _project_root)


def list_collections():
    """List all knowledge sources (collections) from the DB."""
    from rag_shared.db import SessionLocal as SharedSession
    from rag_shared.knowledge_repo import KnowledgeSourceRepo

    db = SharedSession()
    try:
        records = KnowledgeSourceRepo.list_all(db)
        print("\n📋 Available Collections:\n")
        print(f"  {'Name':<35} {'Docs':>5} {'Chunks':>7} {'Status':<12} {'Vector Size':<12}")
        print(f"  {'-'*35} {'-'*5} {'-'*7} {'-'*12} {'-'*12}")
        for r in records:
            print(f"  {r.name:<35} {r.document_count or 0:>5} {r.chunk_count or 0:>7} {r.status or 'unknown':<12} {r.vector_size or '-':<12}")
        return records
    finally:
        db.close()


def evaluate_collection(collection_name: str, output: str = "markdown"):
    """
    Evaluate a collection by triggering a sync and collecting evaluation data.

    This runs the full ingestion sync pipeline on the collection and
    returns evaluation metrics for each file processed.
    """
    import time
    from services.collection_sync_service import sync_collection

    print(f"🚀 Evaluating collection: {collection_name}")
    print(f"   Started at: {datetime.now().isoformat()}")
    t0 = time.time()

    try:
        result = sync_collection(collection_name)
        duration = time.time() - t0
    except Exception as exc:
        print(f"❌ Sync failed: {exc}")
        return

    # Extract summary
    status = result.get("status", "unknown")
    total_added = result.get("added", 0)
    total_updated = result.get("updated", 0)
    total_deleted = result.get("deleted", 0)
    total_unchanged = result.get("unchanged", 0)
    sync_errors = result.get("errors", [])
    message = result.get("message", "")

    print(f"   Completed in {duration:.2f}s")
    print(f"   Status: {status}")
    print(f"   Added: {total_added}, Updated: {total_updated}, Deleted: {total_deleted}, Unchanged: {total_unchanged}")
    if sync_errors:
        print(f"   Errors ({len(sync_errors)}):")
        for e in sync_errors[:5]:
            print(f"     - {e}")
        if len(sync_errors) > 5:
            print(f"     ... and {len(sync_errors) - 5} more")
    if message:
        print(f"   Message: {message}")

    if output == "json":
        # Strip internal data for clean JSON (evaluation data contains Document/Chunk objects)
        safe_result = {
            "collection": result.get("collection"),
            "status": result.get("status"),
            "added": result.get("added"),
            "updated": result.get("updated"),
            "deleted": result.get("deleted"),
            "unchanged": result.get("unchanged"),
            "errors": [str(e) for e in result.get("errors", [])],
            "message": result.get("message", ""),
            "duration_sec": round(duration, 3),
            "connectors_synced": result.get("connectors_synced", []),
        }
        print(f"\n📊 JSON Output:\n{json.dumps(safe_result, indent=2)}")
    elif output == "markdown":
        print(f"\n📊 Evaluation Report for `{collection_name}`")
        print(f"   **Duration:** {duration:.2f}s | **Status:** {status}")
        print(f"   **Files Added:** {total_added} | **Updated:** {total_updated} | **Deleted:** {total_deleted} | **Unchanged:** {total_unchanged}")
        if sync_errors:
            print(f"   **Sync Errors:** {len(sync_errors)}")
    else:
        print(f"\nResult: {json.dumps({k: v for k, v in result.items() if k not in ('evaluation', 'connectors_synced')}, indent=2, default=str)}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate a collection's ingestion pipeline metrics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python scripts/eval_cli.py --collection my-resume-vecstore
  python scripts/eval_cli.py --collection my-resume-vecstore --output json
  python scripts/eval_cli.py --list-collections""",
    )
    parser.add_argument("--collection", type=str, help="Collection (knowledge source) name to evaluate")
    parser.add_argument("--output", type=str, choices=["markdown", "json", "raw"], default="markdown", help="Output format")
    parser.add_argument("--list-collections", action="store_true", help="List available collections and exit")

    args = parser.parse_args()

    if args.list_collections:
        list_collections()
        return

    if not args.collection:
        print("❌ Error: --collection is required (or use --list-collections)")
        parser.print_help()
        sys.exit(1)

    evaluate_collection(args.collection, args.output)


if __name__ == "__main__":
    main()