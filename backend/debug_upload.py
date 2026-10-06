#!/usr/bin/env python3
"""Interactive upload/debug helper for local analyzer testing."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

SCENES = {
    "1": "campus",
    "2": "office",
    "3": "factory",
    "4": "residential",
    "5": "industrial",
    "6": "construction",
}


def choose_image(uploads_dir: Path) -> Path | None:
    images = [
        path
        for path in uploads_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    if not images:
        print(f"No images found under {uploads_dir}")
        return None
    for index, path in enumerate(images[:20], start=1):
        print(f"{index}. {path.name}")
    choice = input("Choose image number: ").strip()
    try:
        return images[int(choice) - 1]
    except Exception:
        print("Invalid image choice")
        return None


def choose_scene() -> str:
    for key, value in SCENES.items():
        print(f"{key}. {value}")
    return SCENES.get(input("Choose scene: ").strip(), "campus")


def main() -> int:
    uploads_dir = Path(__file__).parent / "uploads"
    if not uploads_dir.exists():
        print("uploads directory does not exist")
        return 1
    if not (os.getenv("SILICONFLOW_API_KEY") or os.getenv("DASHSCOPE_API_KEY")):
        print("No provider API key configured; the analyzer may return fallback output.")

    image = choose_image(uploads_dir)
    if not image:
        return 1
    scene = choose_scene()

    from app.services.analyzer import analyzer_service

    result = analyzer_service.analyze_image(str(image), scene=scene, force_refresh=True)
    print("Analysis Results")
    print(f"overall_risk={result.get('overall_risk')}")
    print(f"summary={result.get('summary')}")
    for index, item in enumerate(result.get("items") or [], start=1):
        print(f"{index}. {item.get('type')} [{item.get('risk')}] {item.get('desc')}")
        if item.get("suggest"):
            print(f"   suggest: {item.get('suggest')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
