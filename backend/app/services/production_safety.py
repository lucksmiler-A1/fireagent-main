from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Dict, List

from app.core.config import settings


class ProductionSafetyService:
    def __init__(self) -> None:
        self._topics: List[Dict[str, Any]] = []
        self._updated_at: str = ""
        self._load()

    def _load(self) -> None:
        path = settings.PRODUCTION_SAFETY_FILE
        self._topics = []
        self._updated_at = ""
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f) if f else {}
        except Exception:
            return

        self._updated_at = str(data.get("updated_at", ""))
        rows = data.get("topics")
        if isinstance(rows, list):
            self._topics = [x for x in rows if isinstance(x, dict)]

    @staticmethod
    def _normalize_scene(scene: str) -> str:
        raw = str(scene or "").strip().lower()
        alias = {
            "factory": "industrial",
            "site": "construction",
            "construction_site": "construction",
            "plant": "industrial",
        }
        return alias.get(raw, raw)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        lowered = str(text or "").lower()
        ascii_tokens = re.findall(r"[a-z0-9_+-]+", lowered)
        cjk_tokens = re.findall(r"[\u4e00-\u9fff]{1,6}", lowered)
        return ascii_tokens + cjk_tokens

    def _score_topic(self, topic: Dict[str, Any], scene: str, message: str) -> Dict[str, Any]:
        message_text = str(message or "").lower()
        message_tokens = self._tokenize(message_text)
        token_counter = Counter(message_tokens)

        keywords = [str(x).strip().lower() for x in (topic.get("keywords") or []) if str(x).strip()]
        keyword_hits: List[str] = []
        keyword_score = 0.0
        for kw in keywords:
            if not kw:
                continue
            if " " in kw:
                if kw in message_text:
                    keyword_hits.append(kw)
                    keyword_score += 1.4
            else:
                hit = token_counter.get(kw, 0)
                if hit:
                    keyword_hits.append(kw)
                    keyword_score += min(1.2, 0.6 + 0.3 * hit)

        scene_set = {self._normalize_scene(x) for x in (topic.get("scene") or []) if str(x).strip()}
        scene_score = 0.8 if self._normalize_scene(scene) in scene_set else 0.0
        total = round(keyword_score + scene_score, 4)

        return {
            "id": str(topic.get("id", "")),
            "domain": str(topic.get("domain", "")),
            "title": str(topic.get("title", "")),
            "score": total,
            "scene_match": scene_score > 0,
            "keyword_hits": keyword_hits[:8],
            "qa_points": [str(x) for x in (topic.get("qa_points") or [])][:5],
            "actions": [str(x) for x in (topic.get("actions") or [])][:5],
            "risk_signal": [str(x) for x in (topic.get("risk_signal") or [])][:5],
        }

    def build_context(self, scene: str, message: str, top_k: int | None = None) -> Dict[str, Any]:
        normalized_scene = self._normalize_scene(scene)
        budget = max(1, min(int(top_k or settings.PRODUCTION_SAFETY_TOP_K), 10))

        if normalized_scene not in {"construction", "industrial"}:
            return {
                "enabled": False,
                "scene": normalized_scene,
                "count": 0,
                "topics": [],
                "updated_at": self._updated_at,
                "reason": "scene_not_targeted",
            }

        scored = [self._score_topic(topic, normalized_scene, message) for topic in self._topics]
        scored.sort(
            key=lambda x: (
                float(x.get("score", 0.0)),
                bool(x.get("scene_match")),
                len(x.get("keyword_hits") or []),
            ),
            reverse=True,
        )
        selected = [x for x in scored if float(x.get("score", 0.0)) > 0][:budget]
        if not selected:
            selected = [x for x in scored if bool(x.get("scene_match"))][: min(budget, 3)]

        return {
            "enabled": True,
            "scene": normalized_scene,
            "count": len(selected),
            "topics": selected,
            "updated_at": self._updated_at,
        }


production_safety_service = ProductionSafetyService()

