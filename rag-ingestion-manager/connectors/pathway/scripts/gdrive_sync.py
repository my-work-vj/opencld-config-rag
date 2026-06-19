"""Sync Google Drive files via Pathway pw.io.gdrive into a local directory (Docker)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pathway as pw

from pathway_utils import subscribe_row_dict

SUPPORTED_EXTENSIONS = {
    ".pdf", ".txt", ".md", ".html", ".htm", ".doc", ".docx", ".xlsx", ".pptx", ".csv",
}
EXPORT_MIMES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
}


def _is_supported(meta: dict, name: str) -> bool:
    mime = meta.get("mimeType", "")
    if mime in EXPORT_MIMES:
        return True
    ext = Path(name).suffix.lower()
    return ext in SUPPORTED_EXTENSIONS or mime.startswith("text/")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--object-id", required=True)
    parser.add_argument("--credentials", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    table = pw.io.gdrive.read(
        object_id=args.object_id,
        service_user_credentials_file=args.credentials,
        mode="static",
        format="binary",
        with_metadata=True,
    )

    synced: list[dict] = []
    errors: list[str] = []
    discovered = 0

    def on_change(key, row, time, is_addition):
        nonlocal discovered
        if not is_addition:
            return
        row_data = subscribe_row_dict(row)
        meta = row_data.get("_metadata") or {}
        name = meta.get("path") or meta.get("name") or meta.get("id", "file")
        if not _is_supported(meta, name):
            return
        discovered += 1
        try:
            data = row_data.get("data")
            if data is None:
                return
            if isinstance(data, memoryview):
                payload = bytes(data)
            elif isinstance(data, bytes):
                payload = data
            else:
                payload = bytes(data)

            safe_name = str(name).replace("/", "_").replace("\\", "_")
            dest = out_dir / safe_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)

            synced.append({
                "external_id": meta.get("id", safe_name),
                "name": name,
                "mime_type": meta.get("mimeType", ""),
                "local_path": str(dest),
                "size_bytes": len(payload),
            })
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    pw.io.subscribe(table, on_change)
    pw.run()

    result = {
        "files_discovered": discovered,
        "files_synced": len(synced),
        "errors": errors,
        "message": f"Synced {len(synced)}/{discovered} files from Google Drive via Pathway",
        "synced_files": synced,
        "object_id": args.object_id,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({
            "files_discovered": 0,
            "files_synced": 0,
            "errors": [str(exc)],
            "message": str(exc),
            "synced_files": [],
        }))
        sys.exit(1)
