"""Database models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Record(Base):
    """Image analysis history record."""

    __tablename__ = "records"

    record_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    scene: Mapped[str] = mapped_column(String(50), nullable=False, default="campus")
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    annotated_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    overall_risk: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    items_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Record(record_id='{self.record_id}', risk='{self.overall_risk}')>"


class ChatSession(Base):
    """Short-term conversation memory.

    Thesis §5.7.2: Task Memory state is anchored to the session — current goal,
    last planner intent, and a goal_version that bumps on scene/goal resets.
    """

    __tablename__ = "chat_sessions"

    session_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    scene: Mapped[str] = mapped_column(String(50), nullable=False, default="campus")
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="消防助手会话")
    last_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    current_task_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    current_task_intent_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    goal_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    goal_reset_reason: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ChatMessage(Base):
    """Conversation turns persisted per session.

    Thesis §5.7.3: short-term memory stores "raw text + summary + metadata".
    Metadata persisted per assistant turn: rules_query, evidence_ids,
    guardrail decision — enables structured audit instead of log scraping.
    """

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    used_tools_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    citations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    rules_query: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    guardrail_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class MemoryTask(Base):
    """Task memory for remediation and review."""

    __tablename__ = "memory_tasks"

    task_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    hazard_type: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    action_plan_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CoreMemoryRule(Base):
    """Core memory rule. Editable system-level constraint, scoped by `scope`.

    `scope` is either "global" (applies to every scene) or a scene id
    (campus / dormitory / industrial / construction / ...). This is the
    persistent, write-capable counterpart to the static rule list — modelled
    after MemGPT's editable core memory but bounded to a small, ordered set.
    """

    __tablename__ = "core_memory_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(40), nullable=False, default="global", index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="seed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<CoreMemoryRule(id={self.id}, scope='{self.scope}', priority={self.priority})>"


class RiskProfile(Base):
    """Long-term risk memory aggregated by scene and hazard type."""

    __tablename__ = "risk_profiles"
    __table_args__ = (UniqueConstraint("scene", "hazard_type", name="uq_risk_profile_scene_hazard"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    hazard_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    count_7d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    count_30d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    effective_actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
