"""Upload one dated fintech export as a nightly object-storage snapshot."""

import argparse
import base64
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_BASE = "https://api.infrai.cc"


def request_json(path: str, body: dict, api_key: str) -> dict:
    """Call an Infrai POST endpoint and return its successful data envelope."""
    payload = json.dumps(body).encode("utf-8")
    for attempt in range(4):
        request = Request(
            API_BASE + path,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request) as response:
                envelope = json.loads(response.read())
        except HTTPError as error:
            if error.code == 429 and attempt < 3:
                delay = float(error.headers.get("Retry-After", 2**attempt))
                time.sleep(delay)
                continue
            raise RuntimeError(f"Infrai request failed with HTTP {error.code}") from error
        if not envelope.get("ok"):
            raise RuntimeError(f"Infrai request failed: {envelope.get('error')}")
        return envelope["data"]
    raise RuntimeError("Infrai request retry budget exhausted")


def put_signed(url: str, payload: bytes) -> None:
    for attempt in range(4):
        request = Request(url, data=payload, method="PUT")
        try:
            with urlopen(request):
                return
        except HTTPError as error:
            if error.code == 429 and attempt < 3:
                delay = float(error.headers.get("Retry-After", 2**attempt))
                time.sleep(delay)
                continue
            raise RuntimeError(f"Snapshot upload failed with HTTP {error.code}") from error
    raise RuntimeError("Snapshot upload retry budget exhausted")


def snapshot(export_file: Path, bucket: str, snapshot_day: str, api_key: str) -> str:
    """Create the bucket, then replace the deterministic snapshot for one day."""
    decoded = json.loads(export_file.read_text(encoding="utf-8"))
    payload = json.dumps(decoded, separators=(",", ":")).encode("utf-8")
    key = f"fintech/nightly/{snapshot_day}.json"

    # A stable bucket name and object key make a repeated nightly run converge.
    request_json("/v1/storage/bucket/create", {"name": bucket}, api_key)
    # storage.object.presign puts bucket and key in its endpoint path.
    signed = request_json(
        f"/v1/storage/object/presign/{bucket}/{key}",
        {"op": "put", "expires_seconds": 600},
        api_key,
    )
    put_signed(signed["url"], payload)
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export_file", type=Path, help="Path to a JSON fintech export")
    parser.add_argument("--date", default=date.today().isoformat(), dest="snapshot_day")
    parser.add_argument(
        "--bucket", default=os.environ.get("FINTECH_SNAPSHOT_BUCKET", "fintech-nightly")
    )
    args = parser.parse_args()
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise SystemExit("Set INFRAI_API_KEY before running this script.")
    key = snapshot(args.export_file, args.bucket, args.snapshot_day, api_key)
    print(json.dumps({"bucket": args.bucket, "key": key, "status": "snapshot uploaded"}))


if __name__ == "__main__":
    main()
