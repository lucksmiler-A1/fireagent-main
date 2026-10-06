from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict

from app.core.config import settings


class ResultCacheService:
    def __init__(self) -> None:
        self.enabled = settings.RESULT_CACHE_ENABLED
        self.ttl_seconds = max(int(settings.RESULT_CACHE_TTL_SECONDS), 0)
        self.cache_dir = settings.RESULT_CACHE_DIR
        self._lock = Lock()

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_image_hash(file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def normalize_scene(scene: str) -> str:
        normalized = str(scene or "").strip().lower()
        if not normalized:
            return "campus"
        return "".join(ch if ch.isalnum() else "_" for ch in normalized)

    def _cache_key(self, scene: str, image_hash: str) -> str:
        return f"{self.normalize_scene(scene)}__{image_hash}"

    def _cache_file(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, scene: str, image_hash: str) -> Dict[str, Any] | None:
        if not self.enabled:
            return None

        cache_key = self._cache_key(scene, image_hash)
        cache_file = self._cache_file(cache_key)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return None

        expires_at = float(payload.get("expires_at", 0) or 0)
        if expires_at and time.time() > expires_at:
            try:
                cache_file.unlink(missing_ok=True)
            except Exception:
                pass
            return None

        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        return data

    def set(self, scene: str, image_hash: str, data: Dict[str, Any]) -> None:
        if not self.enabled or self.ttl_seconds <= 0:
            return

        cache_key = self._cache_key(scene, image_hash)
        cache_file = self._cache_file(cache_key)
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        now = int(time.time())
        payload = {
            "scene": self.normalize_scene(scene),
            "image_hash": image_hash,
            "cached_at": now,
            "expires_at": now + self.ttl_seconds,
            "data": data,
        }

        temp_file = cache_file.with_suffix(".tmp")
        try:
            with self._lock:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
                temp_file.replace(cache_file)
        except Exception:
            try:
                temp_file.unlink(missing_ok=True)
            except Exception:
                pass

    def clear_all(self) -> int:
        """Clear all cached analysis result files and return deleted count."""
        if not self.enabled:
            return 0

        deleted = 0
        if not self.cache_dir.exists():
            return 0

        with self._lock:
            for file_path in self.cache_dir.glob("*.json"):
                try:
                    file_path.unlink(missing_ok=True)
                    deleted += 1
                except Exception:
                    continue
        return deleted


result_cache_service = ResultCacheService()
