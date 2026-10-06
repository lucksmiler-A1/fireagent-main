"""Database CRUD helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db import models, schemas


def _parse_items_json(raw: str) -> List[Dict[str, Any]]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
    except Exception:
        return []
    return []


def get_record(db: Session, record_id: str) -> Optional[models.Record]:
    return db.query(models.Record).filter(models.Record.record_id == record_id).first()


def get_records(db: Session, skip: int = 0, limit: int = 100) -> List[models.Record]:
    return (
        db.query(models.Record)
        .order_by(desc(models.Record.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_records_count(db: Session) -> int:
    return db.query(models.Record).count()


def get_records_with_limit_offset(
    db: Session,
    limit: int = 20,
    offset: int = 0,
) -> List[models.Record]:
    return (
        db.query(models.Record)
        .order_by(desc(models.Record.created_at))
        .limit(limit)
        .offset(offset)
        .all()
    )


def create_record(db: Session, record: schemas.RecordCreate) -> models.Record:
    db_record = models.Record(
        record_id=record.record_id,
        scene=record.scene,
        file_path=record.file_path,
        image_url=record.image_url,
        annotated_url=record.annotated_url,
        overall_risk=record.overall_risk,
        summary=record.summary,
        items_json=json.dumps([item.model_dump() for item in record.items], ensure_ascii=False),
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


def update_record(
    db: Session,
    record_id: str,
    record_update: schemas.RecordUpdate,
) -> Optional[models.Record]:
    db_record = get_record(db, record_id)
    if not db_record:
        return None

    update_data = record_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "items" and value is not None:
            db_record.items_json = json.dumps([x.model_dump() for x in value], ensure_ascii=False)
        elif hasattr(db_record, field):
            setattr(db_record, field, value)

    db.commit()
    db.refresh(db_record)
    return db_record


def delete_record(db: Session, record_id: str) -> bool:
    db_record = get_record(db, record_id)
    if not db_record:
        return False

    db.delete(db_record)
    db.commit()
    return True


def delete_all_records(db: Session) -> Tuple[int, List[str]]:
    """Delete all records and return deleted count with file paths."""
    rows = db.query(models.Record).all()
    if not rows:
        return 0, []

    file_paths = [x.file_path for x in rows if getattr(x, "file_path", None)]
    deleted_count = len(rows)

    for row in rows:
        db.delete(row)
    db.commit()

    return deleted_count, file_paths


def count_hazard_occurrences(db: Session, *, scene: str, hazard_type: str, days: int = 30) -> int:
    hazard = str(hazard_type or "").strip()
    if not hazard:
        return 0

    cutoff = datetime.utcnow()
    if days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)

    query = db.query(models.Record).filter(models.Record.created_at >= cutoff)
    if scene:
        query = query.filter(models.Record.scene == scene)

    count = 0
    for row in query.all():
        items = _parse_items_json(getattr(row, "items_json", ""))
        if any(str(item.get("type", "")).strip() == hazard for item in items):
            count += 1
    return count


def get_chat_session(db: Session, session_id: str) -> Optional[models.ChatSession]:
    return db.query(models.ChatSession).filter(models.ChatSession.session_id == session_id).first()


def create_or_get_chat_session(
    db: Session,
    session_id: str,
    *,
    scene: str = "campus",
    title: str = "消防助手会话",
) -> models.ChatSession:
    session = get_chat_session(db, session_id)
    if session:
        return session

    now = datetime.utcnow()
    session = models.ChatSession(
        session_id=session_id,
        scene=scene,
        title=title,
        created_at=now,
        updated_at=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def update_chat_session_summary(
    db: Session,
    session_id: str,
    *,
    summary: str,
    scene: Optional[str] = None,
) -> Optional[models.ChatSession]:
    session = get_chat_session(db, session_id)
    if not session:
        return None

    session.last_summary = summary
    session.updated_at = datetime.utcnow()
    if scene:
        session.scene = scene
    db.commit()
    db.refresh(session)
    return session


def list_chat_messages(db: Session, session_id: str, limit: int = 20) -> List[models.ChatMessage]:
    return (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == session_id)
        .order_by(desc(models.ChatMessage.created_at), desc(models.ChatMessage.id))
        .limit(limit)
        .all()
    )


def append_chat_message(
    db: Session,
    *,
    session_id: str,
    role: str,
    content: str,
    used_tools: Optional[List[str]] = None,
    citations: Optional[List[dict]] = None,
    rules_query: str = "",
    evidence_ids: Optional[List[str]] = None,
    guardrail: Optional[dict] = None,
) -> models.ChatMessage:
    message = models.ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        used_tools_json=json.dumps(used_tools or [], ensure_ascii=False),
        citations_json=json.dumps(citations or [], ensure_ascii=False),
        rules_query=str(rules_query or "")[:1000],
        evidence_ids_json=json.dumps(list(evidence_ids or []), ensure_ascii=False),
        guardrail_json=json.dumps(dict(guardrail or {}), ensure_ascii=False),
        created_at=datetime.utcnow(),
    )
    db.add(message)

    session = get_chat_session(db, session_id)
    if session:
        session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(message)
    return message


def update_chat_session_task_state(
    db: Session,
    session_id: str,
    *,
    goal: Optional[str] = None,
    intent: Optional[dict] = None,
    reset_reason: Optional[str] = None,
    bump_version: bool = False,
    new_scene: Optional[str] = None,
) -> Optional[models.ChatSession]:
    """Update the Task Memory state attached to a session.

    Bumps `goal_version` and records `reset_reason` when the planner re-anchors
    the session (e.g., scene change, explicit goal change).
    """
    session = get_chat_session(db, session_id)
    if not session:
        return None
    if goal is not None:
        session.current_task_goal = str(goal)[:1000]
    if intent is not None:
        session.current_task_intent_json = json.dumps(dict(intent), ensure_ascii=False)
    if reset_reason is not None:
        session.goal_reset_reason = str(reset_reason)[:60]
    if bump_version:
        session.goal_version = int(getattr(session, "goal_version", 1) or 1) + 1
    if new_scene:
        session.scene = str(new_scene)[:50]
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


def clear_all_chat_state(db: Session) -> Dict[str, int]:
    """Truncate every session and message — used by the admin /memory/clear
    endpoint used by the memory management API."""
    msgs = db.query(models.ChatMessage).delete()
    sessions = db.query(models.ChatSession).delete()
    db.commit()
    return {"deleted_messages": int(msgs or 0), "deleted_sessions": int(sessions or 0)}


def get_risk_profile(db: Session, *, scene: str, hazard_type: str) -> Optional[models.RiskProfile]:
    return (
        db.query(models.RiskProfile)
        .filter(models.RiskProfile.scene == scene, models.RiskProfile.hazard_type == hazard_type)
        .first()
    )


def list_risk_profiles(db: Session, *, scene: Optional[str] = None, limit: int = 20) -> List[models.RiskProfile]:
    query = db.query(models.RiskProfile)
    if scene:
        query = query.filter(models.RiskProfile.scene == scene)
    return (
        query.order_by(
            desc(models.RiskProfile.count_30d),
            desc(models.RiskProfile.count_7d),
            desc(models.RiskProfile.updated_at),
        )
        .limit(max(1, min(limit, 200)))
        .all()
    )


def upsert_risk_profile(
    db: Session,
    *,
    scene: str,
    hazard_type: str,
    count_7d: int,
    count_30d: int,
    last_seen_at: Optional[datetime] = None,
    last_summary: str = "",
    effective_actions: Optional[List[str]] = None,
) -> models.RiskProfile:
    profile = get_risk_profile(db, scene=scene, hazard_type=hazard_type)
    now = datetime.utcnow()
    if not profile:
        profile = models.RiskProfile(
            scene=scene,
            hazard_type=hazard_type,
            count_7d=max(0, int(count_7d)),
            count_30d=max(0, int(count_30d)),
            last_seen_at=last_seen_at,
            last_summary=last_summary,
            effective_actions_json=json.dumps(effective_actions or [], ensure_ascii=False),
            updated_at=now,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    profile.count_7d = max(0, int(count_7d))
    profile.count_30d = max(0, int(count_30d))
    if last_seen_at:
        profile.last_seen_at = last_seen_at
    if last_summary:
        profile.last_summary = last_summary
    if effective_actions is not None:
        profile.effective_actions_json = json.dumps(effective_actions, ensure_ascii=False)
    profile.updated_at = now
    db.commit()
    db.refresh(profile)
    return profile


def get_memory_task(db: Session, task_id: str) -> Optional[models.MemoryTask]:
    return db.query(models.MemoryTask).filter(models.MemoryTask.task_id == task_id).first()


def get_memory_task_by_source_hazard(
    db: Session,
    *,
    source_record_id: Optional[str],
    hazard_type: str,
) -> Optional[models.MemoryTask]:
    if not source_record_id or not hazard_type:
        return None
    return (
        db.query(models.MemoryTask)
        .filter(
            models.MemoryTask.source_record_id == source_record_id,
            models.MemoryTask.hazard_type == hazard_type,
        )
        .order_by(desc(models.MemoryTask.updated_at))
        .first()
    )


def list_memory_tasks(
    db: Session,
    *,
    status: Optional[str] = None,
    scene: Optional[str] = None,
    limit: int = 30,
) -> List[models.MemoryTask]:
    query = db.query(models.MemoryTask)
    if status:
        query = query.filter(models.MemoryTask.status == status)
    if scene:
        query = query.join(
            models.Record,
            models.Record.record_id == models.MemoryTask.source_record_id,
            isouter=True,
        ).filter(models.Record.scene == scene)
    return query.order_by(desc(models.MemoryTask.updated_at)).limit(max(1, min(limit, 300))).all()


def create_or_update_memory_task(
    db: Session,
    *,
    source_record_id: Optional[str],
    hazard_type: str,
    title: str,
    priority: int = 2,
    status: str = "open",
    action_plan: Optional[List[str]] = None,
    due_at: Optional[datetime] = None,
    review_at: Optional[datetime] = None,
    session_id: Optional[str] = None,
) -> models.MemoryTask:
    task = get_memory_task_by_source_hazard(
        db,
        source_record_id=source_record_id,
        hazard_type=hazard_type,
    )

    now = datetime.utcnow()
    if not task:
        task = models.MemoryTask(
            task_id=f"t_{uuid.uuid4().hex[:10]}",
            session_id=session_id,
            source_record_id=source_record_id,
            title=title,
            hazard_type=hazard_type,
            priority=max(1, min(int(priority), 3)),
            status=status,
            action_plan_json=json.dumps(action_plan or [], ensure_ascii=False),
            due_at=due_at,
            review_at=review_at,
            created_at=now,
            updated_at=now,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    task.title = title or task.title
    task.priority = max(1, min(int(priority), 3))
    task.status = status or task.status
    if action_plan is not None:
        task.action_plan_json = json.dumps(action_plan, ensure_ascii=False)
    if due_at is not None:
        task.due_at = due_at
    if review_at is not None:
        task.review_at = review_at
    if session_id:
        task.session_id = session_id
    task.updated_at = now
    db.commit()
    db.refresh(task)
    return task


def update_memory_task_status(db: Session, *, task_id: str, status: str) -> Optional[models.MemoryTask]:
    task = get_memory_task(db, task_id)
    if not task:
        return None
    task.status = status
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


def delete_all_memory_state(db: Session) -> Dict[str, int]:
    tasks = db.query(models.MemoryTask).delete()
    profiles = db.query(models.RiskProfile).delete()
    db.commit()
    return {"deleted_tasks": int(tasks or 0), "deleted_profiles": int(profiles or 0)}


# --------------- Core Memory Rules ---------------

def list_core_memory_rules(
    db: Session,
    *,
    scope: Optional[str] = None,
    include_disabled: bool = False,
) -> List[models.CoreMemoryRule]:
    """List core-memory rules. If `scope` is given, returns rules that apply to
    that scope plus all "global" rules; otherwise returns every rule."""
    query = db.query(models.CoreMemoryRule)
    if not include_disabled:
        query = query.filter(models.CoreMemoryRule.enabled == True)  # noqa: E712
    if scope:
        query = query.filter(models.CoreMemoryRule.scope.in_([scope, "global"]))
    return (
        query.order_by(
            models.CoreMemoryRule.priority.asc(),
            models.CoreMemoryRule.id.asc(),
        ).all()
    )


def get_core_memory_rule(db: Session, rule_id: int) -> Optional[models.CoreMemoryRule]:
    return db.query(models.CoreMemoryRule).filter(models.CoreMemoryRule.id == rule_id).first()


def add_core_memory_rule(
    db: Session,
    *,
    scope: str,
    text: str,
    priority: int = 5,
    source: str = "user",
) -> models.CoreMemoryRule:
    now = datetime.utcnow()
    rule = models.CoreMemoryRule(
        scope=str(scope or "global").strip().lower() or "global",
        text=str(text or "").strip(),
        priority=max(1, min(int(priority), 10)),
        enabled=True,
        source=str(source or "user").strip()[:40] or "user",
        created_at=now,
        updated_at=now,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_core_memory_rule(
    db: Session,
    *,
    rule_id: int,
    text: Optional[str] = None,
    priority: Optional[int] = None,
    enabled: Optional[bool] = None,
    scope: Optional[str] = None,
) -> Optional[models.CoreMemoryRule]:
    rule = get_core_memory_rule(db, rule_id)
    if not rule:
        return None
    if text is not None:
        rule.text = str(text).strip()
    if priority is not None:
        rule.priority = max(1, min(int(priority), 10))
    if enabled is not None:
        rule.enabled = bool(enabled)
    if scope is not None:
        rule.scope = str(scope).strip().lower() or "global"
    rule.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rule)
    return rule


def delete_core_memory_rule(db: Session, rule_id: int) -> bool:
    rule = get_core_memory_rule(db, rule_id)
    if not rule:
        return False
    db.delete(rule)
    db.commit()
    return True


def count_core_memory_rules(db: Session) -> int:
    return db.query(models.CoreMemoryRule).count()
