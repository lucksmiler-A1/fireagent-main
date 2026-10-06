#!/usr/bin/env python3
"""Smoke test SiliconFlow-backed image analysis without hardcoded secrets."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))


def main() -> int:
    if not os.getenv("SILICONFLOW_API_KEY"):
        print("SILICONFLOW_API_KEY is not configured.")
        print('$env:SILICONFLOW_API_KEY="your_key_here"')
        return 1

    from app.services.analyzer import analyzer_service

    uploads_dir = Path(__file__).parent / "uploads"
    candidates = [
        path
        for path in uploads_dir.glob("*")
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    if not candidates:
        print(f"No test images found under {uploads_dir}")
        return 1

    test_image = candidates[0]
    print("Testing SiliconFlow API with configured key.")
    print(f"Analyzing image: {test_image}")
    result = analyzer_service.analyze_image(str(test_image), scene="campus", force_refresh=True)
    print("Analysis Result:")
    print(f"overall_risk={result.get('overall_risk')}")
    print(f"summary={result.get('summary')}")
    print(f"items={len(result.get('items') or [])}")
    return 0 if result.get("overall_risk") in {"safe", "warning", "danger"} else 1


if __name__ == "__main__":
    sys.exit(main())
