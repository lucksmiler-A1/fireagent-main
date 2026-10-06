from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import crud, models


class LongTermMemoryService:
    def __init__(self) -> None:
        self.base_url = settings.SILICONFLOW_BASE_URL.rstrip("/")
        self.embedding_model = settings.LONG_MEMORY_EMBEDDING_MODEL or settings.RAG_EMBEDDING_MODEL
        self.cache_dir = settings.LONG_MEMORY_CACHE_DIR
        self.index_file = settings.LONG_MEMORY_INDEX_FILE
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_text(value: Any, max_len: int = 500) -> str:
        return str(value or "").strip()[:max_len]

    @staticmethod
    def _parse_items(raw_items: str) -> List[Dict[str, Any]]:
        if not raw_items:
            return []
        try:
            parsed = json.loads(raw_items)
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
        except Exception:
            return []
        return []

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        normalized = str(text or "").lower()
        return re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", normalized)

    @staticmethod
    def _cosine(vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        norm_a = math.sqrt(sum(x * x for x in vec_a))
        norm_b = math.sqrt(sum(x * x for x in vec_b))
        if norm_a <= 0 or norm_b <= 0:
            return 0.0
        dot = sum(vec_a[idx] * vec_b[idx] for idx in range(len(vec_a)))
        return float(dot / (norm_a * norm_b))

    @staticmethod
    def _normalize_risk(value: Any) -> str:
        mapping = {
            "safe": "safe",
            "warning": "warning",
            "danger": "danger",
            "low": "safe",
            "medium": "warning",
            "high": "danger",
            "\u4f4e": "safe",
            "\u4e2d": "warning",
            "\u9ad8": "danger",
        }
        key = str(value or "").strip().lower()
        return mapping.get(key, "warning")

    def _get_api_key(self) -> str:
        return str(settings.SILICONFLOW_API_KEY or os.getenv("SILICONFLOW_API_KEY") or "").strip()

    def _embedding_request(self, api_key: str, inputs: List[str]) -> Dict[str, Any]:
        payload = {
            "model": self.embedding_model,
            "input": inputs,
            "encoding_format": "float",
        }

        try:
            response = requests.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
        except requests.RequestException as exc:
            return {"ok": False, "error": f"request_failed: {exc}", "vectors": []}

        if response.status_code >= 400:
            return {"ok": False, "error": f"provider_http_{response.status_code}", "vectors": []}

        try:
            body = response.json()
        except Exception:
            return {"ok": False, "error": "invalid_json", "vectors": []}

        rows = body.get("data") or []
        if not isinstance(rows, list):
            return {"ok": False, "error": "invalid_data", "vectors": []}

        pairs: List[Tuple[int, List[float]]] = []
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            embedding = row.get("embedding")
            if not isinstance(embedding, list):
                continue
            try:
                vec = [float(x) for x in embedding]
            except Exception:
                continue
            pairs.append((int(row.get("index", idx) or idx), vec))

        pairs.sort(key=lambda x: x[0])
        vectors = [vec for _, vec in pairs]
        if len(vectors) != len(inputs):
            return {"ok": False, "error": "embedding_count_mismatch", "vectors": vectors}
        return {"ok": True, "vectors": vectors}

    def _case_doc_from_record(self, row: models.Record) -> Dict[str, Any]:
        items = self._parse_items(getattr(row, "items_json", ""))
        hazards = [self._safe_text(item.get("type"), 80) for item in items if self._safe_text(item.get("type"), 80)]
        suggestions = [self._safe_text(item.get("suggest"), 120) for item in items if self._safe_text(item.get("suggest"), 120)]
        descriptions = [self._safe_text(item.get("desc"), 160) for item in items if self._safe_text(item.get("desc"), 160)]

        scene = self._safe_text(getattr(row, "scene", ""), 40)
        overall_risk = self._safe_text(getattr(row, "overall_risk", ""), 20)
        summary = self._safe_text(getattr(row, "summary", ""), 600)

        doc_text_parts = [
            f"scene:{scene}",
            f"risk:{overall_risk}",
            summary,
            " ".join(hazards[:6]),
            " ".join(descriptions[:6]),
            " ".join(suggestions[:4]),
        ]

        doc_text = " ".join([x for x in doc_text_parts if x]).strip()
        record_id = getattr(row, "record_id", "") or ""

        return {
            "record_id": record_id,
            "scene": scene,
            "overall_risk": overall_risk,
            "summary": summary,
            "hazards": hazards[:6],
            "created_at": getattr(row, "created_at", None).isoformat() if getattr(row, "created_at", None) else "",
            "doc_text": doc_text,
            "_sig": self._record_signature(record_id, doc_text),
        }

    def _record_signature(self, record_id: str, doc_text: str) -> str:
        """Per-record signature: changes when record content changes, but is
        stable across additions of unrelated records. Enables incremental
        embedding instead of full-cache invalidation."""
        hasher = hashlib.sha256()
        hasher.update(self.embedding_model.encode("utf-8"))
        hasher.update(b"|")
        hasher.update(str(record_id or "").encode("utf-8", errors="ignore"))
        hasher.update(b"|")
        hasher.update(str(doc_text or "").encode("utf-8", errors="ignore"))
        return hasher.hexdigest()[:24]

    def _build_docs_signature(self, docs: List[Dict[str, Any]]) -> str:
        """Aggregate signature over all current docs. Used as a fingerprint
        of the current corpus state for diagnostics (not for cache hit/miss
        decisions — those use per-record signatures)."""
        hasher = hashlib.sha256()
        hasher.update(self.embedding_model.encode("utf-8"))
        for sig in sorted(self._safe_text(doc.get("_sig"), 32) for doc in docs):
            hasher.update(sig.encode("utf-8"))
        return hasher.hexdigest()[:24]

    def _load_index(self) -> Dict[str, Any]:
        if not self.index_file.exists():
            return {}
        try:
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_index(self, payload: Dict[str, Any]) -> None:
        temp_file = self.index_file.with_suffix(".tmp")
        try:
            temp_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temp_file.replace(self.index_file)
        except Exception:
            try:
                temp_file.unlink(missing_ok=True)
            except Exception:
                pass

    def clear_embedding_index(self) -> bool:
        try:
            self.index_file.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    def _ensure_case_index(self, db: Session, api_key: str) -> Dict[str, Any]:
        """Build or extend the per-record embedding index.

        Incremental strategy:
          1. Pull current records → compute per-record signature.
          2. Load cached `{sig: vector}` map.
          3. Embed only records whose signature is missing from the cache.
          4. Drop signatures that no longer exist (evicted records).
          5. Persist the updated map.

        This replaces the previous "any change invalidates everything" behaviour
        that caused full re-embedding on every new upload.
        """
        rows = crud.get_records_with_limit_offset(
            db,
            limit=max(50, min(int(settings.LONG_MEMORY_MAX_CASES), 5000)),
            offset=0,
        )
        docs = [self._case_doc_from_record(row) for row in rows]
        signature = self._build_docs_signature(docs)

        empty_stats = {
            "total_records": len(docs),
            "cached_hits": 0,
            "newly_embedded": 0,
            "evicted": 0,
            "cache_size_before": 0,
            "cache_size_after": 0,
        }

        if not docs:
            return {"docs": [], "vectors": [], "mode": "empty", "signature": signature, "stats": empty_stats}

        if not (settings.LONG_MEMORY_ENABLE_EMBEDDING and api_key):
            return {"docs": docs, "vectors": [], "mode": "lexical", "signature": signature, "stats": empty_stats}

        # Load existing per-record vector cache.
        cached = self._load_index()
        cached_map: Dict[str, List[float]] = {}
        cached_model = cached.get("model")
        if cached_model == self.embedding_model and isinstance(cached.get("embeddings"), dict):
            for sig_key, vec in cached["embeddings"].items():
                if isinstance(vec, list):
                    cached_map[str(sig_key)] = vec
        elif cached_model == self.embedding_model and isinstance(cached.get("vectors"), list):
            # Legacy format (full-rebuild era): treat as cold cache. The new
            # incremental builds will populate per-record entries lazily.
            cached_map = {}

        cache_size_before = len(cached_map)

        # Find records that still need an embedding.
        missing_indices: List[int] = []
        missing_texts: List[str] = []
        for idx, doc in enumerate(docs):
            sig = doc.get("_sig", "")
            if sig and sig not in cached_map:
                missing_indices.append(idx)
                missing_texts.append(self._safe_text(doc.get("doc_text"), 2000))

        new_vectors_by_sig: Dict[str, List[float]] = {}
        embed_error: Optional[str] = None
        if missing_texts:
            batch_size = max(int(settings.LONG_MEMORY_BATCH_SIZE), 1)
            embedded: List[List[float]] = []
            for start in range(0, len(missing_texts), batch_size):
                batch = missing_texts[start : start + batch_size]
                result = self._embedding_request(api_key, batch)
                if not result.get("ok"):
                    embed_error = str(result.get("error") or "embedding_failed")
                    break
                vectors_chunk = result.get("vectors") or []
                if len(vectors_chunk) != len(batch):
                    embed_error = "embedding_count_mismatch"
                    break
                embedded.extend(vectors_chunk)
            if embed_error is None:
                for offset, sig_idx in enumerate(missing_indices):
                    sig = docs[sig_idx].get("_sig", "")
                    if sig and offset < len(embedded):
                        new_vectors_by_sig[sig] = embedded[offset]

        # Drop signatures that no longer correspond to a live record.
        current_sigs = {doc.get("_sig", "") for doc in docs if doc.get("_sig")}
        retained_map = {sig: vec for sig, vec in cached_map.items() if sig in current_sigs}
        evicted = len(cached_map) - len(retained_map)
        retained_map.update(new_vectors_by_sig)

        # Build vectors aligned with docs order; if any record is still missing
        # (e.g. embedding API failed for one batch), fall back to lexical mode.
        aligned_vectors: List[List[float]] = []
        coverage_complete = True
        for doc in docs:
            sig = doc.get("_sig", "")
            vec = retained_map.get(sig)
            if vec is None:
                coverage_complete = False
                break
            aligned_vectors.append(vec)

        # Persist only if there was a change.
        if missing_indices or evicted:
            self._save_index(
                {
                    "model": self.embedding_model,
                    "updated_at": datetime.utcnow().isoformat(),
                    "doc_count": len(docs),
                    "embeddings": retained_map,
                    "signature": signature,
                }
            )

        stats = {
            "total_records": len(docs),
            "cached_hits": len(docs) - len(missing_indices),
            "newly_embedded": len(new_vectors_by_sig),
            "evicted": evicted,
            "cache_size_before": cache_size_before,
            "cache_size_after": len(retained_map),
        }

        if not coverage_complete:
            return {
                "docs": docs,
                "vectors": [],
                "mode": f"lexical_fallback:{embed_error or 'partial_embedding'}",
                "signature": signature,
                "stats": stats,
            }

        if not missing_indices:
            mode = "embedding_cache"
        elif cache_size_before == 0:
            mode = "embedding_fresh"
        else:
            mode = "embedding_incremental"

        return {
            "docs": docs,
            "vectors": aligned_vectors,
            "mode": mode,
            "signature": signature,
            "stats": stats,
        }

    def retrieve_similar_cases(self, db: Session, *, query: str, scene: str, limit: int = 3) -> Dict[str, Any]:
        clean_query = self._safe_text(query, 800)
        if not clean_query:
            return {"mode": "empty_query", "cases": [], "stats": {}}

        api_key = self._get_api_key()
        index_bundle = self._ensure_case_index(db, api_key)
        docs = index_bundle.get("docs") or []
        vectors = index_bundle.get("vectors") or []
        mode = str(index_bundle.get("mode", "lexical"))
        signature = index_bundle.get("signature", "")
        index_stats = index_bundle.get("stats") or {}

        if not docs:
            return {"mode": mode, "signature": signature, "cases": [], "stats": index_stats}

        scored: List[Dict[str, Any]] = []
        scene_bonus = float(settings.LONG_MEMORY_SCENE_BONUS)
        target_scene = self._safe_text(scene, 40).lower()

        # Thesis §5.7.4: score = μ · sim_dense + (1 − μ) · sim_lex + scene_bonus.
        # μ defaults to 0.8 when vector retrieval is healthy; μ degrades to 0
        # when the embedding service is unavailable, leaving pure lexical
        # overlap as the safety fallback.
        mu_configured = max(0.0, min(float(settings.LONG_MEMORY_MU), 1.0))
        mu_effective = 0.0

        query_vec: List[float] = []
        if vectors and settings.LONG_MEMORY_ENABLE_EMBEDDING and api_key:
            query_vec_result = self._embedding_request(api_key, [clean_query])
            if query_vec_result.get("ok") and query_vec_result.get("vectors"):
                query_vec = query_vec_result["vectors"][0]
                mu_effective = mu_configured
            else:
                mode = "lexical_due_to_query_embedding"

        query_tokens = set(self._tokenize(clean_query))
        for idx, doc in enumerate(docs):
            doc_text = self._safe_text(doc.get("doc_text"), 2000)
            doc_tokens = set(self._tokenize(doc_text))
            overlap = len(query_tokens & doc_tokens)
            sim_lex = float(overlap / max(1, len(query_tokens)))

            sim_dense = 0.0
            if query_vec and idx < len(vectors) and vectors[idx]:
                sim_dense = self._cosine(query_vec, vectors[idx])

            score = mu_effective * sim_dense + (1.0 - mu_effective) * sim_lex
            same_scene = self._safe_text(doc.get("scene"), 40).lower() == target_scene
            if same_scene:
                score += scene_bonus

            # Keep the document if it has any positive signal (dense or lexical)
            # or if it matches the requested scene — same admission rule as
            # before, just unified across both branches.
            if score > 0 or sim_dense > 0 or sim_lex > 0 or same_scene:
                scored.append(
                    {
                        **doc,
                        "score": round(float(score), 4),
                        "sim_dense": round(float(sim_dense), 4),
                        "sim_lex": round(float(sim_lex), 4),
                    }
                )

        if mu_effective > 0:
            mode = f"hybrid_mu={mu_effective:.2f}"
        elif mode in {"embedding_cache", "embedding_fresh", "embedding_incremental"}:
            # Index was built but query-side embedding failed → degrade label.
            mode = f"lexical_fallback_mu=0:{mode}"
        else:
            mode = "lexical_mu=0"

        scored.sort(key=lambda x: (float(x.get("score", 0.0)), x.get("created_at", "")), reverse=True)
        top_k = max(1, min(int(limit), 8))
        cases = [
            {
                "record_id": item.get("record_id", ""),
                "scene": item.get("scene", ""),
                "overall_risk": item.get("overall_risk", ""),
                "summary": self._safe_text(item.get("summary"), 240),
                "hazards": item.get("hazards", [])[:4],
                "score": float(item.get("score", 0.0)),
                "created_at": item.get("created_at", ""),
            }
            for item in scored[:top_k]
        ]

        return {
            "mode": mode,
            "signature": signature,
            "cases": cases,
            "candidate_count": len(scored),
            "stats": index_stats,
        }

    def _build_profile_summary(self, profiles: List[models.RiskProfile]) -> str:
        if not profiles:
            return "No long-term hazard profile yet."
        top = sorted(profiles, key=lambda x: (getattr(x, "count_30d", 0), getattr(x, "count_7d", 0)), reverse=True)[:3]
        chunks = [
            f"{self._safe_text(item.hazard_type, 60)}({int(getattr(item, 'count_30d', 0))}/30d)"
            for item in top
        ]
        return "Top recurring hazards: " + ", ".join(chunks)

    def build_long_term_context(self, db: Session, *, query: str, scene: str) -> Dict[str, Any]:
        profiles = crud.list_risk_profiles(db, scene=scene, limit=12)
        open_tasks = crud.list_memory_tasks(db, status="open", scene=scene, limit=12)
        similar = self.retrieve_similar_cases(db, query=query, scene=scene, limit=settings.LONG_MEMORY_TOP_K)
        index_stats = similar.get("stats") or {}

        profile_items = [
            {
                "scene": self._safe_text(item.scene, 40),
                "hazard_type": self._safe_text(item.hazard_type, 80),
                "count_7d": int(getattr(item, "count_7d", 0)),
                "count_30d": int(getattr(item, "count_30d", 0)),
                "last_summary": self._safe_text(getattr(item, "last_summary", ""), 220),
                "updated_at": getattr(item, "updated_at", None).isoformat() if getattr(item, "updated_at", None) else "",
            }
            for item in profiles
        ]
        recurring = [x for x in profile_items if x.get("count_30d", 0) >= 2][:5]

        task_items = []
        for task in open_tasks:
            action_plan: List[str] = []
            try:
                parsed = json.loads(getattr(task, "action_plan_json", "[]") or "[]")
                if isinstance(parsed, list):
                    action_plan = [self._safe_text(x, 120) for x in parsed[:4]]
            except Exception:
                action_plan = []

            task_items.append(
                {
                    "task_id": self._safe_text(getattr(task, "task_id", ""), 60),
                    "source_record_id": self._safe_text(getattr(task, "source_record_id", ""), 60),
                    "hazard_type": self._safe_text(getattr(task, "hazard_type", ""), 80),
                    "priority": int(getattr(task, "priority", 2)),
                    "status": self._safe_text(getattr(task, "status", "open"), 20),
                    "title": self._safe_text(getattr(task, "title", ""), 180),
                    "action_plan": action_plan,
                    "updated_at": getattr(task, "updated_at", None).isoformat() if getattr(task, "updated_at", None) else "",
                }
            )

        return {
            "profiles": profile_items,
            "open_tasks": task_items,
            "recurring_hazards": recurring,
            "similar_cases": similar.get("cases", []),
            "similar_cases_mode": similar.get("mode", ""),
            "similar_cases_signature": similar.get("signature", ""),
            "summary": self._build_profile_summary(profiles),
            "index_stats": index_stats,
        }

    def update_from_record(self, db: Session, record: models.Record) -> Dict[str, Any]:
        scene = self._safe_text(getattr(record, "scene", ""), 40) or "campus"
        created_at = getattr(record, "created_at", None) or datetime.utcnow()
        summary = self._safe_text(getattr(record, "summary", ""), 260)
        items = self._parse_items(getattr(record, "items_json", ""))

        hazards = []
        for item in items:
            hazard_type = self._safe_text(item.get("type"), 80)
            if hazard_type:
                hazards.append(hazard_type)
        unique_hazards = list(dict.fromkeys(hazards))

        updated_profiles = 0
        for hazard in unique_hazards:
            count_7d = crud.count_hazard_occurrences(db, scene=scene, hazard_type=hazard, days=7)
            count_30d = crud.count_hazard_occurrences(db, scene=scene, hazard_type=hazard, days=30)
            crud.upsert_risk_profile(
                db,
                scene=scene,
                hazard_type=hazard,
                count_7d=count_7d,
                count_30d=count_30d,
                last_seen_at=created_at,
                last_summary=summary,
            )
            updated_profiles += 1

        updated_tasks = 0
        for item in items:
            hazard_type = self._safe_text(item.get("type"), 80)
            if not hazard_type:
                continue
            risk = self._normalize_risk(item.get("risk"))
            if risk == "safe":
                continue
            priority = 1 if risk == "danger" else 2
            desc = self._safe_text(item.get("desc"), 140)
            suggest = self._safe_text(item.get("suggest"), 160)
            action_plan = [x for x in [suggest, "On-site recheck with photo evidence", "Close task after remediation"] if x]
            title = f"[{scene}] {hazard_type}: {desc or suggest or 'pending remediation'}"
            crud.create_or_update_memory_task(
                db,
                source_record_id=self._safe_text(getattr(record, "record_id", ""), 60),
                hazard_type=hazard_type,
                title=title,
                priority=priority,
                status="open",
                action_plan=action_plan,
                due_at=created_at + timedelta(days=7 if priority == 1 else 14),
            )
            updated_tasks += 1

        # NOTE: Previous versions called self.clear_embedding_index() here,
        # which forced a full re-embedding of every historical record on the
        # next query. We now rely on per-record incremental signatures in
        # `_ensure_case_index`: the new record will be embedded lazily on the
        # next access and merged into the existing vector cache, while old
        # vectors remain valid.

        return {
            "updated_profiles": updated_profiles,
            "updated_tasks": updated_tasks,
            "hazard_count": len(unique_hazards),
        }

    def rebuild_index(self, db: Session) -> Dict[str, Any]:
        api_key = self._get_api_key()
        self.clear_embedding_index()
        bundle = self._ensure_case_index(db, api_key)
        return {
            "mode": bundle.get("mode", ""),
            "signature": bundle.get("signature", ""),
            "doc_count": len(bundle.get("docs") or []),
            "vector_count": len(bundle.get("vectors") or []),
        }


long_term_memory_service = LongTermMemoryService()
