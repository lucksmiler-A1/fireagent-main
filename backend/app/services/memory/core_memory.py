"""Core Memory layer.

Persistent, editable, scope-aware system-level constraints for the agent.
This is the writable counterpart to the static rule list — inspired by
MemGPT's editable core memory, but bounded to a small ordered set per scope.

Lookup order:
  1. If a DB session is provided, return rules from `core_memory_rules` table
     (filtered to scope + "global", ordered by priority).
  2. Otherwise, return the built-in defaults.

The defaults below are also used to seed the table on first startup.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session


# Built-in safety defaults. Used both as the cold-start seed for the DB-backed
# table and as the fallback when no DB session is available.
DEFAULT_CORE_RULES: List[Dict[str, Any]] = [
    {
        "scope": "global",
        "priority": 1,
        "text": "Use only tool outputs and provided context; do not invent legal clauses, penalties, or scene facts.",
    },
    {
        "scope": "global",
        "priority": 2,
        "text": "Citations must come from rules_context in the current turn; if no rule is retrieved, do not output citations.",
    },
    {
        "scope": "global",
        "priority": 3,
        "text": "If evidence is insufficient, explicitly say the answer is inconclusive or more on-site detail is required.",
    },
    {
        "scope": "global",
        "priority": 4,
        "text": "Remediation advice is a safety-management suggestion, not an enforcement or legal judgment.",
    },
    {
        "scope": "global",
        "priority": 5,
        "text": "For high-risk hazards, prefer conservative and actionable safety guidance.",
    },
    # Scene-specific defaults — small examples that demonstrate the per-scene
    # override capability. Edit these from the API / admin panel as needed.
    {
        "scope": "industrial",
        "priority": 2,
        "text": "Prioritize temporary-power, hot-work, lifting, and confined-space hazards before generic recommendations.",
    },
    {
        "scope": "construction",
        "priority": 2,
        "text": "Always reference site-specific switch-box, PPE and scaffold standards before general fire codes.",
    },
    {
        "scope": "campus",
        "priority": 2,
        "text": "Pay extra attention to dormitory charging, corridor obstruction, and evening unattended appliances.",
    },
]

# Legacy alias — kept so external code that imports CORE_MEMORY_RULES still works.
CORE_MEMORY_RULES: List[str] = [item["text"] for item in DEFAULT_CORE_RULES if item["scope"] == "global"]


def _safe_text(value: Any, max_len: int = 4000) -> str:
    return str(value or "").strip()[:max_len]


def core_rules(db: Optional[Session] = None, scene: Optional[str] = None) -> List[str]:
    """Return the active core rules.

    - If `db` is provided, read from `core_memory_rules`, scoped to
      `scene` (plus "global"). Returns text strings ordered by priority.
    - If `db` is None or any error occurs, returns the built-in defaults
      (global only, to stay safe and deterministic).
    """
    if db is None:
        return [item["text"] for item in DEFAULT_CORE_RULES if item["scope"] == "global"]

    try:
        # Local import to avoid circular import with app.db package init.
        from app.db import crud

        scope = (scene or "").strip().lower() or None
        rows = crud.list_core_memory_rules(db, scope=scope)
        if rows:
            return [_safe_text(getattr(r, "text", ""), 800) for r in rows if _safe_text(getattr(r, "text", ""))]
    except Exception:
        pass

    return [item["text"] for item in DEFAULT_CORE_RULES if item["scope"] == "global"]


def core_rules_detailed(db: Session, scene: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return active core rules with metadata (id, scope, priority, source).

    Used by the snapshot/admin endpoints so the UI can show edit affordances.
    Falls back to in-memory defaults if the DB is empty or unreadable.
    """
    try:
        from app.db import crud

        scope = (scene or "").strip().lower() or None
        rows = crud.list_core_memory_rules(db, scope=scope)
        if rows:
            return [
                {
                    "id": int(getattr(r, "id", 0)),
                    "scope": _safe_text(getattr(r, "scope", "global"), 40),
                    "priority": int(getattr(r, "priority", 5)),
                    "text": _safe_text(getattr(r, "text", ""), 800),
                    "enabled": bool(getattr(r, "enabled", True)),
                    "source": _safe_text(getattr(r, "source", "seed"), 40),
                    "updated_at": getattr(r, "updated_at", None).isoformat() if getattr(r, "updated_at", None) else "",
                }
                for r in rows
            ]
    except Exception:
        pass

    return [
        {
            "id": None,
            "scope": item["scope"],
            "priority": item["priority"],
            "text": item["text"],
            "enabled": True,
            "source": "default_fallback",
            "updated_at": "",
        }
        for item in DEFAULT_CORE_RULES
        if item["scope"] == "global"
    ]


def seed_default_core_rules(db: Session) -> int:
    """Seed the `core_memory_rules` table with DEFAULT_CORE_RULES if empty.
    Returns the number of inserted rows."""
    try:
        from app.db import crud

        if crud.count_core_memory_rules(db) > 0:
            return 0
        inserted = 0
        for item in DEFAULT_CORE_RULES:
            crud.add_core_memory_rule(
                db,
                scope=item["scope"],
                text=item["text"],
                priority=item["priority"],
                source="seed",
            )
            inserted += 1
        return inserted
    except Exception:
        return 0


def apply_guardrails(
    *,
    question: str,
    reply: str,
    rules_context: Optional[Dict[str, Any]],
    citations: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Lightweight reply guardrail.

    If the user explicitly asks for legal grounding but no rule was retrieved,
    prepend a transparency note and drop any model-fabricated citations.
    """
    final_reply = _safe_text(reply, 4000)
    final_citations = list(citations)

    asks_for_rules = any(
        word in str(question or "")
        for word in [
            "法规",  # 法规
            "依据",  # 依据
            "条款",  # 条款
            "规范",  # 规范
            "消防法",  # 消防法
            "处罚",  # 处罚
            "rule",
            "citation",
        ]
    )
    has_rule_evidence = bool(rules_context and rules_context.get("rules"))
    if asks_for_rules and not has_rule_evidence:
        final_reply = (
            "No sufficient rule evidence was retrieved for a definitive clause-level answer."
            f"{(' ' + final_reply) if final_reply else ''}"
        ).strip()
        final_citations = []

    if not has_rule_evidence:
        final_citations = []

    return {"reply": final_reply, "citations": final_citations}
