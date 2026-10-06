from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import crud


class ShortTermMemoryService:
    @staticmethod
    def _safe_text(value: Any, max_len: int = 600) -> str:
        return str(value or "").strip()[:max_len]

    @staticmethod
    def _parse_json_list(raw_value: str) -> List[Any]:
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return []
        return []

    @staticmethod
    def _parse_json_obj(raw_value: str) -> Dict[str, Any]:
        if not raw_value:
            return {}
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
        return {}

    def _llm_summary(self, scene: str, messages: List[Dict[str, Any]]) -> str:
        """Thesis §5.7.3: optional small-LLM summary, periodically refreshed.

        Falls back silently to the deterministic stitched summary when:
        - the feature is disabled,
        - the API key is missing,
        - the provider call fails or returns malformed content.
        """
        api_key = (settings.SILICONFLOW_API_KEY or os.getenv("SILICONFLOW_API_KEY") or "").strip()
        if not api_key:
            return ""

        snippet_lines: List[str] = []
        for item in messages[-8:]:
            role = "U" if str(item.get("role")) != "assistant" else "A"
            content = self._safe_text(item.get("content"), 240)
            if content:
                snippet_lines.append(f"{role}: {content}")
        if not snippet_lines:
            return ""

        prompt = (
            "Summarize the following fire-safety inspection conversation in 2-3 short Chinese sentences. "
            "Focus on the user's current focus, any hazards mentioned, and outstanding follow-ups. "
            "Do not invent facts. Respond with plain text, no JSON, no markdown.\n\n"
            f"Scene: {scene}\n" + "\n".join(snippet_lines)
        )

        try:
            response = requests.post(
                f"{settings.SILICONFLOW_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.SILICONFLOW_TEXT_MODEL,
                    "messages": [
                        {"role": "system", "content": "You write concise factual session summaries."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": int(settings.SHORT_MEMORY_SUMMARY_MAX_TOKENS),
                },
                timeout=30,
            )
        except requests.RequestException:
            return ""

        if response.status_code >= 400:
            return ""
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except Exception:
            return ""
        return self._safe_text(content, 500)

    def _build_summary(
        self,
        scene: str,
        current_record_context: Optional[Dict[str, Any]],
        messages: List[Dict[str, Any]],
    ) -> str:
        topics: List[str] = []
        if current_record_context and current_record_context.get("found"):
            record = current_record_context.get("record") or {}
            summary = self._safe_text(record.get("summary"), 120)
            if summary:
                topics.append(f"Current record summary: {summary}")

        user_messages = [
            self._safe_text(item.get("content"), 80)
            for item in messages
            if item.get("role") == "user"
        ]
        if user_messages:
            topics.append(f"Recent user focus: {'; '.join(user_messages[-3:])}")

        if not topics:
            topics.append("This session is mainly about fire-risk recognition, legal grounding, and remediation guidance.")

        return self._safe_text(f"Scene: {scene}. {' '.join(topics)}", 500)

    def load(
        self,
        db: Session,
        *,
        session_id: str,
        scene: str,
        history_messages: List[Dict[str, str]],
        current_record_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        session = crud.create_or_get_chat_session(db, session_id, scene=scene)
        rows = crud.list_chat_messages(db, session_id, limit=12)

        persisted_messages: List[Dict[str, Any]] = []
        for row in reversed(rows):
            persisted_messages.append(
                {
                    "role": str(getattr(row, "role", "user")),
                    "content": self._safe_text(getattr(row, "content", ""), 600),
                    "used_tools": self._parse_json_list(getattr(row, "used_tools_json", "")),
                    "citations": self._parse_json_list(getattr(row, "citations_json", "")),
                    # Thesis §5.7.3: structured metadata travels with each turn
                    # so audits work on fields, not raw log text.
                    "metadata": {
                        "rules_query": self._safe_text(getattr(row, "rules_query", ""), 600),
                        "evidence_ids": self._parse_json_list(getattr(row, "evidence_ids_json", "")),
                        "guardrail": self._parse_json_obj(getattr(row, "guardrail_json", "")),
                    },
                }
            )

        merged: List[Dict[str, Any]] = []
        seen_pairs = set()
        for item in persisted_messages + list(history_messages or []):
            role = "assistant" if str(item.get("role")) == "assistant" else "user"
            content = self._safe_text(item.get("content"), 600)
            if not content:
                continue
            pair = (role, content)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            entry: Dict[str, Any] = {"role": role, "content": content}
            # Carry the per-turn audit metadata through if the DB row had one.
            # In-process history (`history_messages`) typically has no metadata,
            # so we only attach it when present and dict-shaped.
            metadata = item.get("metadata")
            if isinstance(metadata, dict) and metadata:
                entry["metadata"] = metadata
            merged.append(entry)

        merged = merged[-10:]
        summary = self._safe_text(getattr(session, "last_summary", ""), 500)
        if not summary:
            summary = self._build_summary(scene, current_record_context, merged)
            crud.update_chat_session_summary(db, session_id, summary=summary, scene=scene)

        return {
            "session_id": session_id,
            "summary": summary,
            "recent_messages": merged,
            "message_count": len(merged),
        }

    def persist(
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
        crud.create_or_get_chat_session(db, session_id, scene=scene)
        crud.append_chat_message(db, session_id=session_id, role="user", content=user_message)
        crud.append_chat_message(
            db,
            session_id=session_id,
            role="assistant",
            content=assistant_reply,
            used_tools=used_tools,
            citations=citations,
            rules_query=rules_query,
            evidence_ids=evidence_ids,
            guardrail=guardrail,
        )

        merged_messages = (
            short_term_memory.get("recent_messages", [])
            + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_reply},
            ]
        )
        stitched_summary = self._build_summary(scene, current_record_context, merged_messages)

        # Thesis §5.7.3: refresh the LLM-generated summary every N turns when
        # enabled; otherwise the deterministic stitched summary is canonical.
        updated_summary = stitched_summary
        if settings.SHORT_MEMORY_LLM_SUMMARY:
            turn_count = len([m for m in merged_messages if str(m.get("role")) == "user"])
            interval = max(1, int(settings.SHORT_MEMORY_SUMMARY_EVERY_N))
            if turn_count % interval == 0:
                llm_text = self._llm_summary(scene, merged_messages)
                if llm_text:
                    updated_summary = llm_text

        crud.update_chat_session_summary(db, session_id, summary=updated_summary, scene=scene)
        return updated_summary


short_term_memory_service = ShortTermMemoryService()
