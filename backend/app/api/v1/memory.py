from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import crud
from app.db.schemas import (
    CoreMemoryCreateRequest,
    CoreMemoryListResponse,
    CoreMemoryRuleItem,
    CoreMemoryUpdateRequest,
    MemoryOverviewResponse,
    MemorySnapshotCore,
    MemorySnapshotLongTerm,
    MemorySnapshotResponse,
    MemorySnapshotShortTerm,
    MemorySnapshotStats,
    MemorySnapshotTask,
    MemoryTaskItem,
    MemoryTaskListResponse,
    RiskProfileItem,
    SimilarCaseItem,
)
from app.db.session import get_db
from app.services.memory import memory_manager
from app.services.memory.core_memory import core_rules_detailed
from app.services.memory.long_term_memory import long_term_memory_service
from app.services.memory.short_term_memory import short_term_memory_service
from app.services.memory.task_memory import build_task_context

router = APIRouter()


def _safe_text(value, max_len: int = 220) -> str:
    return str(value or "").strip()[:max_len]


def require_admin(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> None:
    """Thesis §5.7.1: writes to Core Memory require admin permission.

    Reject the request unless the configured ADMIN_TOKEN matches the
    X-Admin-Token header. When ADMIN_TOKEN is unset, every mutating endpoint
    is locked — read-only by default. This is intentional: an unconfigured
    deployment must not allow anonymous edits to the system constitution.
    """
    expected = (settings.ADMIN_TOKEN or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Core memory writes are disabled: set ADMIN_TOKEN to enable admin operations.",
        )
    if not x_admin_token or x_admin_token.strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token.")


@router.get("/overview", response_model=MemoryOverviewResponse)
def get_memory_overview(
    scene: str = Query("campus", max_length=40),
    query: str = Query("", max_length=800),
    db: Session = Depends(get_db),
):
    data = long_term_memory_service.build_long_term_context(db, query=query or scene, scene=scene)

    profiles = [RiskProfileItem(**item) for item in data.get("profiles", [])]
    recurring_hazards = [RiskProfileItem(**item) for item in data.get("recurring_hazards", [])]
    open_tasks = [MemoryTaskItem(**item) for item in data.get("open_tasks", [])]
    similar_cases = [SimilarCaseItem(**item) for item in data.get("similar_cases", [])]

    return MemoryOverviewResponse(
        summary=_safe_text(data.get("summary"), 260),
        recurring_hazards=recurring_hazards,
        profiles=profiles,
        open_tasks=open_tasks,
        similar_cases=similar_cases,
        similar_cases_mode=_safe_text(data.get("similar_cases_mode"), 80),
        similar_cases_signature=_safe_text(data.get("similar_cases_signature"), 80),
    )


@router.get("/snapshot", response_model=MemorySnapshotResponse)
def get_memory_snapshot(
    scene: str = Query("campus", max_length=40),
    session_id: str = Query("", max_length=60),
    query: str = Query("", max_length=800),
    db: Session = Depends(get_db),
):
    """Return a unified snapshot of all four memory layers.

    Designed for the demo/inspection panel: a single call gives the UI
    everything needed to display the full memory state for the current
    (scene, session, query) triplet.
    """
    scene_norm = (scene or "campus").strip().lower() or "campus"
    user_query = (query or "").strip()

    # ---- Core memory (DB-backed, scope-aware) ----
    core_items = core_rules_detailed(db, scene=scene_norm)
    core_rule_items = [CoreMemoryRuleItem(**item) for item in core_items]
    core_layer = MemorySnapshotCore(
        scope=scene_norm,
        rules=core_rule_items,
        is_persisted=any(item.id is not None for item in core_rule_items),
    )

    # ---- Short-term memory (per-session) ----
    if session_id:
        st_data = short_term_memory_service.load(
            db,
            session_id=session_id,
            scene=scene_norm,
            history_messages=[],
            current_record_context=None,
        )
    else:
        st_data = {
            "session_id": "",
            "summary": "(no active session — pass session_id to inspect a live conversation)",
            "recent_messages": [],
            "message_count": 0,
        }
    short_term_layer = MemorySnapshotShortTerm(
        session_id=_safe_text(st_data.get("session_id"), 60),
        summary=_safe_text(st_data.get("summary"), 600),
        recent_messages=list(st_data.get("recent_messages") or []),
        message_count=int(st_data.get("message_count") or 0),
    )

    # ---- Task memory (assembled view) ----
    task_data = build_task_context(
        session_id=session_id,
        scene=scene_norm,
        user_message=user_query,
        current_record_context=None,
        short_term_memory=st_data if isinstance(st_data, dict) else {},
        db=db,
    )
    task_layer = MemorySnapshotTask(
        session_id=_safe_text(task_data.get("session_id"), 60),
        scene=_safe_text(task_data.get("scene"), 40),
        user_goal=_safe_text(task_data.get("user_goal"), 240),
        task_goal=_safe_text(task_data.get("task_goal"), 400),
        planner_intent=dict(task_data.get("planner_intent") or {}),
        goal_version=int(task_data.get("goal_version") or 1),
        goal_reset_reason=_safe_text(task_data.get("goal_reset_reason"), 60),
        current_record_id=_safe_text(task_data.get("current_record_id"), 60),
        current_record_risk=_safe_text(task_data.get("current_record_risk"), 40),
        current_record_summary=_safe_text(task_data.get("current_record_summary"), 240),
        short_term_summary=_safe_text(task_data.get("short_term_summary"), 320),
        scene_guide=dict(task_data.get("scene_guide") or {}),
    )

    # ---- Long-term memory (case retrieval + risk profile + open tasks) ----
    lt_data = long_term_memory_service.build_long_term_context(
        db,
        query=user_query or scene_norm,
        scene=scene_norm,
    )
    long_term_layer = MemorySnapshotLongTerm(
        summary=_safe_text(lt_data.get("summary"), 320),
        profiles=[RiskProfileItem(**item) for item in lt_data.get("profiles", [])],
        recurring_hazards=[RiskProfileItem(**item) for item in lt_data.get("recurring_hazards", [])],
        open_tasks=[MemoryTaskItem(**item) for item in lt_data.get("open_tasks", [])],
        similar_cases=[SimilarCaseItem(**item) for item in lt_data.get("similar_cases", [])],
        similar_cases_mode=_safe_text(lt_data.get("similar_cases_mode"), 80),
        similar_cases_signature=_safe_text(lt_data.get("similar_cases_signature"), 80),
        index_stats=dict(lt_data.get("index_stats") or {}),
    )

    # ---- System-level stats ----
    stats = MemorySnapshotStats(
        total_records=crud.get_records_count(db),
        total_profiles=len(crud.list_risk_profiles(db, limit=200)),
        total_open_tasks=len(crud.list_memory_tasks(db, status="open", limit=300)),
        total_core_rules=crud.count_core_memory_rules(db),
    )

    return MemorySnapshotResponse(
        generated_at=datetime.utcnow().isoformat(),
        session_id=session_id,
        scene=scene_norm,
        query=user_query,
        core=core_layer,
        task=task_layer,
        short_term=short_term_layer,
        long_term=long_term_layer,
        stats=stats,
    )


# --------------- Core memory CRUD ---------------

@router.get("/core", response_model=CoreMemoryListResponse)
def list_core_rules(
    scope: str = Query("", max_length=40, description="Scope filter. Empty = all."),
    include_disabled: bool = Query(False),
    db: Session = Depends(get_db),
):
    scope_filter = (scope or "").strip().lower() or None
    rows = crud.list_core_memory_rules(db, scope=scope_filter, include_disabled=include_disabled)
    rules = [
        CoreMemoryRuleItem(
            id=int(getattr(r, "id", 0)),
            scope=_safe_text(getattr(r, "scope", "global"), 40),
            priority=int(getattr(r, "priority", 5)),
            text=_safe_text(getattr(r, "text", ""), 600),
            enabled=bool(getattr(r, "enabled", True)),
            source=_safe_text(getattr(r, "source", "seed"), 40),
            updated_at=getattr(r, "updated_at", None).isoformat() if getattr(r, "updated_at", None) else "",
        )
        for r in rows
    ]
    return CoreMemoryListResponse(scope=scope_filter or "all", total=len(rules), rules=rules)


@router.post("/core", response_model=CoreMemoryRuleItem, status_code=201)
def create_core_rule(
    payload: CoreMemoryCreateRequest,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    rule = crud.add_core_memory_rule(
        db,
        scope=payload.scope,
        text=payload.text,
        priority=payload.priority,
        source="user",
    )
    return CoreMemoryRuleItem(
        id=int(rule.id),
        scope=rule.scope,
        priority=rule.priority,
        text=rule.text,
        enabled=rule.enabled,
        source=rule.source,
        updated_at=rule.updated_at.isoformat() if rule.updated_at else "",
    )


@router.patch("/core/{rule_id}", response_model=CoreMemoryRuleItem)
def update_core_rule(
    rule_id: int,
    payload: CoreMemoryUpdateRequest,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    rule = crud.update_core_memory_rule(
        db,
        rule_id=rule_id,
        text=payload.text,
        priority=payload.priority,
        enabled=payload.enabled,
        scope=payload.scope,
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Core memory rule not found")
    return CoreMemoryRuleItem(
        id=int(rule.id),
        scope=rule.scope,
        priority=rule.priority,
        text=rule.text,
        enabled=rule.enabled,
        source=rule.source,
        updated_at=rule.updated_at.isoformat() if rule.updated_at else "",
    )


@router.delete("/core/{rule_id}")
def delete_core_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    ok = crud.delete_core_memory_rule(db, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Core memory rule not found")
    return {"deleted": True, "rule_id": rule_id}


# --------------- Memory task management ---------------

@router.get("/tasks", response_model=MemoryTaskListResponse)
def list_memory_tasks(
    scene: str = Query("campus", max_length=40),
    status: str = Query("open", max_length=30),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = crud.list_memory_tasks(db, status=status, scene=scene, limit=limit)
    tasks: List[MemoryTaskItem] = []
    for row in rows:
        action_plan = []
        try:
            parsed = json.loads(getattr(row, "action_plan_json", "[]") or "[]")
            if isinstance(parsed, list):
                action_plan = [_safe_text(x, 120) for x in parsed[:4]]
        except Exception:
            action_plan = []
        tasks.append(
            MemoryTaskItem(
                task_id=_safe_text(getattr(row, "task_id", ""), 60),
                source_record_id=_safe_text(getattr(row, "source_record_id", ""), 60),
                hazard_type=_safe_text(getattr(row, "hazard_type", ""), 80),
                priority=int(getattr(row, "priority", 2)),
                status=_safe_text(getattr(row, "status", "open"), 20),
                title=_safe_text(getattr(row, "title", ""), 180),
                action_plan=action_plan,
                updated_at=getattr(row, "updated_at", None).isoformat() if getattr(row, "updated_at", None) else "",
            )
        )
    return MemoryTaskListResponse(total=len(tasks), tasks=tasks)


class MemoryTaskStatusRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=30)


@router.post("/tasks/{task_id}/status", response_model=MemoryTaskItem)
def update_memory_task_status(
    task_id: str,
    payload: MemoryTaskStatusRequest,
    db: Session = Depends(get_db),
):
    row = crud.update_memory_task_status(db, task_id=task_id, status=payload.status)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    action_plan = []
    try:
        parsed = json.loads(getattr(row, "action_plan_json", "[]") or "[]")
        if isinstance(parsed, list):
            action_plan = [_safe_text(x, 120) for x in parsed[:4]]
    except Exception:
        action_plan = []
    return MemoryTaskItem(
        task_id=_safe_text(getattr(row, "task_id", ""), 60),
        source_record_id=_safe_text(getattr(row, "source_record_id", ""), 60),
        hazard_type=_safe_text(getattr(row, "hazard_type", ""), 80),
        priority=int(getattr(row, "priority", 2)),
        status=_safe_text(getattr(row, "status", "open"), 20),
        title=_safe_text(getattr(row, "title", ""), 180),
        action_plan=action_plan,
        updated_at=getattr(row, "updated_at", None).isoformat() if getattr(row, "updated_at", None) else "",
    )


@router.post("/rebuild-index")
def rebuild_long_term_index(db: Session = Depends(get_db)):
    return long_term_memory_service.rebuild_index(db)


@router.post("/clear")
def clear_all_memory(
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    """Admin reset endpoint that wipes every memory layer and
    the long-term embedding cache. Image records are managed separately by
    `/records/clear` and are intentionally NOT touched here."""
    return memory_manager.clear_all(db)
