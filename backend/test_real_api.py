#!/usr/bin/env python3
"""Smoke test the analyzer with a configured provider key.

This script intentionally does not contain or print API keys.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))


def main() -> int:
    if not (os.getenv("SILICONFLOW_API_KEY") or os.getenv("DASHSCOPE_API_KEY")):
        print("ERROR: no provider API key is configured.")
        print("Set SILICONFLOW_API_KEY or DASHSCOPE_API_KEY before running this script.")
        return 1

    uploads_dir = Path(__file__).parent / "uploads"
    if not uploads_dir.exists():
        print("ERROR: uploads directory not found")
        return 1

    image_files = [
        path
        for path in uploads_dir.iterdir()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    if not image_files:
        print("ERROR: no image files found in uploads directory")
        return 1

    test_image = image_files[0]
    print(f"Using test image: {test_image}")

    from app.services.analyzer import analyzer_service

    result = analyzer_service.analyze_image(str(test_image), "campus", force_refresh=True)
    print("Analysis result:")
    print(f"overall_risk={result.get('overall_risk')}")
    print(f"summary={result.get('summary')}")
    print(f"items={len(result.get('items') or [])}")
    return 0 if result.get("overall_risk") in {"safe", "warning", "danger"} else 1


if __name__ == "__main__":
    sys.exit(main())
