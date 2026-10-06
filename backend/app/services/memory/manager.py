from __future__ import annotations

import shutil
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import crud
from app.services.memory.core_memory import apply_guardrails, core_rules, core_rules_detailed
from app.services.memory.long_term_memory import long_term_memory_service
from app.services.memory.short_term_memory import short_term_memory_service
from app.services.memory.task_memory import build_task_context


class MemoryManager:
    @staticmethod
    def _safe_text(value: Any, max_len: int = 500) -> str:
        return str(value or "").strip()[:max_len]

    def core_rules(
        self,
        db: Optional[Session] = None,
        scene: Optional[str] = None,
    ) -> List[str]:
        return core_rules(db=db, scene=scene)

    def core_rules_detailed(
        self,
        db: Session,
        scene: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return core_rules_detailed(db, scene=scene)

    def load_short_term_memory(
        self,
        db: Session,
        *,
        session_id: str,
        scene: str,
        history_messages: List[Dict[str, str]],
        current_record_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return short_term_memory_service.load(
            db,
            session_id=session_id,
            scene=scene,
            history_messages=history_messages,
            current_record_context=current_record_context,
        )

    def persist_short_term_memory(
        self,
        db: Session,
        *,
        session_id: str,
        scene: str,
        user_message: str,
        assistant_reply: str,
        short_term_memory: Dict[str, Any],
        current_record_context: Optional[Dict[str, Any]],
        used_tools: List[str],
        citations: List[Dict[str, str]],
        rules_query: str = "",
        evidence_ids: Optional[List[str]] = None,
        guardrail: Optional[Dict[str, Any]] = None,
    ) -> str:
        return short_term_memory_service.persist(
            db,
            session_id=session_id,
            scene=scene,
            user_message=user_message,
            assistant_reply=assistant_reply,
            short_term_memory=short_term_memory,
            current_record_context=current_record_context,
            used_tools=used_tools,
            citations=citations,
            rules_query=rules_query,
            evidence_ids=evidence_ids,
            guardrail=guardrail,
        )

    def build_task_context(
        self,
        *,
        session_id: str,
        scene: str,
        user_message: str,
        current_record_context: Optional[Dict[str, Any]],
        short_term_memory: Dict[str, Any],
        db: Optional[Session] = None,
        planner_intent: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return build_task_context(
            session_id=session_id,
            scene=scene,
            user_message=user_message,
            current_record_context=current_record_context,
            short_term_memory=short_term_memory,
            db=db,
            planner_intent=planner_intent,
        )

    def build_long_term_context(self, db: Session, *, query: str, scene: str) -> Dict[str, Any]:
        return long_term_memory_service.build_long_term_context(db, query=query, scene=scene)

    def apply_guardrails(
        self,
        *,
        question: str,
        reply: str,
        rules_context: Optional[Dict[str, Any]],
        citations: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        return apply_guardrails(
            question=question,
            reply=reply,
            rules_context=rules_context,
            citations=citations,
        )

    def build_payload(
        self,
        *,
        task_context: Dict[str, Any],
        short_term_memory: Dict[str, Any],
        long_term_memory: Dict[str, Any],
        summary: Optional[str] = None,
        db: Optional[Session] = None,
        scene: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "core": {"rules": self.core_rules(db=db, scene=scene), "scope": scene or "global"},
            "task": dict(task_context),
            "short_term": dict(short_term_memory),
            "long_term": dict(long_term_memory or {}),
        }
        if summary is not None:
            payload["short_term"]["summary"] = self._safe_text(summary, 500)
        return payload

    def route(
        self,
        db: Session,
        *,
        session_id: str,
        scene: str,
        user_message: str,
        history_messages: Optional[List[Dict[str, str]]] = None,
        current_record_context: Optional[Dict[str, Any]] = None,
        planner_intent: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """MemoryRouter — single-call orchestration of the four layers
        (four-layer memory routing).

        Order of operations:
          1. Short-term load (raw + summary + metadata)
          2. Task build/refresh (planner intent + scene-change reset)
          3. Long-term retrieval (μ-weighted hybrid case lookup)
          4. Core rules pinned for the requested scope

        Returns the assembled context every caller needs to compose a prompt
        without coordinating the four sub-modules manually.
        """
        short_term = short_term_memory_service.load(
            db,
            session_id=session_id,
            scene=scene,
            history_messages=history_messages or [],
            current_record_context=current_record_context,
        )
        task = build_task_context(
            session_id=session_id,
            scene=scene,
            user_message=user_message,
            current_record_context=current_record_context,
            short_term_memory=short_term,
            db=db,
            planner_intent=planner_intent,
        )
        long_term = long_term_memory_service.build_long_term_context(
            db,
            query=user_message,
            scene=scene,
        )
        return {
            "core_rules": self.core_rules(db=db, scene=scene),
            "task": task,
            "short_term": short_term,
            "long_term": long_term,
        }

    def clear_all(self, db: Session) -> Dict[str, Any]:
        """Admin entry point that wipes every memory
        layer and the long-term embedding index.

        Records (image history) are intentionally left untouched here: the
        existing `/records/clear` endpoint owns that lifecycle. Operators
        wanting a full reset should call both endpoints back-to-back.
        """
        chat_stats = crud.clear_all_chat_state(db)
        memory_stats = crud.delete_all_memory_state(db)
        index_cleared = long_term_memory_service.clear_embedding_index()

        cache_dir = settings.LONG_MEMORY_CACHE_DIR
        cache_cleared = False
        try:
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_cleared = True
        except Exception:
            cache_cleared = False

        return {
            "deleted_sessions": chat_stats.get("deleted_sessions", 0),
            "deleted_messages": chat_stats.get("deleted_messages", 0),
            "deleted_tasks": memory_stats.get("deleted_tasks", 0),
            "deleted_profiles": memory_stats.get("deleted_profiles", 0),
            "long_term_index_cleared": bool(index_cleared),
            "long_term_cache_cleared": cache_cleared,
        }


memory_manager = MemoryManager()
