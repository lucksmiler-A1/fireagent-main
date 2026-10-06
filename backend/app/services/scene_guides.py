from __future__ import annotations

import json
from typing import Any, Dict, List

from app.core.config import settings


class SceneGuidesService:
    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._guides: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        path = settings.SCENE_GUIDES_FILE
        self._data = {}
        self._guides = {}
        if not path.exists():
            return

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                self._data = json.load(f) if f else {}
        except Exception:
            self._data = {}

        guides = self._data.get("guides") if isinstance(self._data, dict) else None
        if isinstance(guides, dict):
            self._guides = {str(k): v for k, v in guides.items() if isinstance(v, dict)}

    @staticmethod
    def _normalize_scene(scene: str) -> str:
        raw = str(scene or "").strip().lower()
        alias_map = {
            "factory": "industrial",
            "plant": "industrial",
            "industry": "industrial",
            "construction_site": "construction",
            "site": "construction",
            "residence": "residential",
            "home": "residential",
        }
        return alias_map.get(raw, raw)

    def available_scenes(self) -> List[str]:
        return sorted(self._guides.keys())

    def get_guide(self, scene: str) -> Dict[str, Any]:
        key = self._normalize_scene(scene)
        guide = self._guides.get(key)
        if not guide:
            guide = self._guides.get("campus", {})
            key = "campus"

        return {
            "scene": key,
            "title": str(guide.get("title", "")),
            "poem": str(guide.get("poem", "")),
            "focus_area": str(guide.get("focus_area", "")),
            "checklist": list(guide.get("checklist") or []),
            "tips": list(guide.get("tips") or []),
            "available_scenes": self.available_scenes(),
            "updated_at": self._data.get("updated_at", ""),
        }


scene_guides_service = SceneGuidesService()
