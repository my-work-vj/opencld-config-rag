"""Test Google Drive connectivity via Pathway pw.io.gdrive (runs inside Docker)."""

from __future__ import annotations

import argparse
import json
import sys

import pathway as pw

from pathway_utils import subscribe_row_dict


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--object-id", required=True)
    parser.add_argument("--credentials", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    table = pw.io.gdrive.read(
        object_id=args.object_id,
        service_user_credentials_file=args.credentials,
        mode="static",
        format="only_metadata",
        with_metadata=True,
    )

    items: list[dict] = []

    def on_change(key, row, time, is_addition):
        if not is_addition:
            return
        row_data = subscribe_row_dict(row)
        meta = row_data.get("_metadata") or {}
        items.append({
            "id": meta.get("id"),
            "name": meta.get("name"),
            "mime_type": meta.get("mimeType"),
        })

    pw.io.subscribe(table, on_change)
    pw.run()

    result = {
        "ok": True,
        "message": f"Pathway connected to Google Drive folder ({len(items)} file(s) discovered)",
        "object_id": args.object_id,
        "item_count": len(items),
        "sample_items": items[:args.limit],
    }
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "message": str(exc), "item_count": 0, "sample_items": []}))
        sys.exit(1)
