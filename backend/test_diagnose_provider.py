import argparse
import json
import os
import sys
from pathlib import Path

import requests


def _print_header(title: str) -> None:
    print("\n" + "=" * 20 + f" {title} " + "=" * 20)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose AI provider failures for analysis upload.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010", help="Backend base URL")
    parser.add_argument("--image", required=True, help="Path to image file")
    parser.add_argument("--scene", default="campus", help="Scene hint")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    image_path = Path(args.image).expanduser()
    if not image_path.exists():
        print(f"[ERROR] Image not found: {image_path}")
        return 2

    _print_header("Health Check")
    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        print(f"GET /health -> {resp.status_code} {resp.text.strip()}")
    except Exception as exc:
        print(f"[ERROR] Health check failed: {exc}")

    _print_header("Upload + Analyze")
    try:
        with open(image_path, "rb") as f:
            files = {"file": (image_path.name, f, "application/octet-stream")}
            data = {"scene": args.scene}
            resp = requests.post(f"{base_url}/api/v1/analysis/upload", files=files, data=data, timeout=120)
    except Exception as exc:
        print(f"[ERROR] Request failed: {exc}")
        return 3

    print(f"POST /api/v1/analysis/upload -> {resp.status_code}")
    text = resp.text.strip()
    if not text:
        print("[ERROR] Empty response body.")
        return 4

    try:
        payload = resp.json()
    except Exception:
        print("[RAW RESPONSE]")
        print(text[:4000])
        return 5

    print("[SUMMARY]")
    print(f"overall_risk: {payload.get('overall_risk')}")
    print(f"summary: {payload.get('summary')}")

    debug = payload.get("_debug") or {}
    if debug:
        _print_header("Debug")
        print(json.dumps(debug, ensure_ascii=False, indent=2)[:4000])
        print()
        if debug.get("error"):
            print(f"[DEBUG ERROR] {debug.get('error')}")
    else:
        print("[WARN] No _debug found in response.")

    if resp.status_code >= 400:
        _print_header("Error Body")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:4000])
        return 6

    return 0


if __name__ == "__main__":
    sys.exit(main())
