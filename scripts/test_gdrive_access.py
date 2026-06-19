"""Direct Google Drive API access test (service account)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from google.auth.transport.requests import Request
from google.oauth2 import service_account

CREDS = r"c:\Users\2782234\CursorProjects\opncld-rag\sanguine-robot-499610-q7-b777bdf1ad75.json"
FOLDER_ID = "14IXHBDpExTdBDfh5GTKmQEIiv6AYHRMG"
SCOPE = "https://www.googleapis.com/auth/drive.readonly"


def get_token() -> tuple[str, str]:
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=[SCOPE])
    creds.refresh(Request())
    return creds.token, creds.service_account_email


def curl_get(url: str, token: str) -> tuple[int | str, str]:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def main() -> None:
    token, email = get_token()
    print(f"Service account: {email}")
    print(f"Folder ID: {FOLDER_ID}")
    print(f"\nEquivalent curl (folder metadata):")
    print(
        f'curl -H "Authorization: Bearer <TOKEN>" '
        f'"https://www.googleapis.com/drive/v3/files/{FOLDER_ID}'
        f'?fields=id,name,mimeType,shared&supportsAllDrives=true"'
    )

    url1 = (
        f"https://www.googleapis.com/drive/v3/files/{FOLDER_ID}"
        f"?fields=id,name,mimeType,shared,owners,permissions&supportsAllDrives=true"
    )
    status1, body1 = curl_get(url1, token)
    print("\n=== GET folder metadata ===")
    print("HTTP", status1)
    try:
        print(json.dumps(json.loads(body1), indent=2))
    except json.JSONDecodeError:
        print(body1)

    q = urllib.parse.quote(f"'{FOLDER_ID}' in parents and trashed=false")
    url2 = (
        f"https://www.googleapis.com/drive/v3/files?q={q}"
        f"&fields=files(id,name,mimeType,size,modifiedTime)"
        f"&pageSize=100&supportsAllDrives=true&includeItemsFromAllDrives=true"
    )
    status2, body2 = curl_get(url2, token)
    print("\n=== LIST files in folder ===")
    print("HTTP", status2)
    try:
        data = json.loads(body2)
        print(json.dumps(data, indent=2))
        files = data.get("files", [])
        print(f"\nFile count: {len(files)}")
    except json.JSONDecodeError:
        print(body2)

    if status1 != 200 or status2 != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
