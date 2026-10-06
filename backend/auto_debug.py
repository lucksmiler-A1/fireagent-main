#!/usr/bin/env python3
"""Run a local analyzer smoke test against the first image in backend/uploads.

Secrets are never hardcoded here. Configure provider keys through environment
variables before running the script.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))


def auto_analyze() -> bool:
    print("=== Auto Debug: Fire Hazard Detection ===")
    if not os.getenv("SILICONFLOW_API_KEY") and not os.getenv("DASHSCOPE_API_KEY"):
        print("ERROR: no provider API key is configured.")
        print("Set SILICONFLOW_API_KEY or DASHSCOPE_API_KEY before running this script.")
        return False

    uploads_dir = Path(__file__).parent / "uploads"
    if not uploads_dir.exists():
        print("ERROR: uploads directory not found")
        return False

    image_files = [
        path
        for path in uploads_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    if not image_files:
        print("ERROR: no image files found")
        return False

    selected_image = image_files[0]
    scene = "campus"
    print(f"Selected image: {selected_image.name}")
    print(f"Selected scene: {scene}")

    try:
        from app.services.analyzer import analyzer_service
    except ImportError as exc:
        print(f"Import failed: {exc}")
        return False

    try:
        result = analyzer_service.analyze_image(str(selected_image), scene, force_refresh=True)
    except Exception as exc:
        print(f"Analysis failed: {exc}")
        return False

    print("Analysis Results:")
    print(f"Overall Risk Level: {result.get('overall_risk')}")
    print(f"Summary: {result.get('summary')}")
    print(f"Number of Hazards Found: {len(result.get('items') or [])}")
    return True


if __name__ == "__main__":
    sys.exit(0 if auto_analyze() else 1)
