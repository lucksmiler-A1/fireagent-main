from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RecordItem(BaseModel):
    type: str = Field(..., description="Hazard type")
    risk: str = Field(..., description="Risk level")
    desc: str = Field(..., description="Hazard description")
    suggest: Optional[str] = Field(None, description="Suggestion")


class Citation(BaseModel):
    article: str = Field(..., description="Rule article id")
    source: str = Field(..., description="Rule document")
    quote: str = Field(..., description="Supporting text")


class RecordBase(BaseModel):
    record_id: str
    scene: str
    file_path: str
    image_url: str
    annotated_url: Optional[str] = None
    overall_risk: str
    summary: str
    items: List[RecordItem] = Field(default_factory=list)


class RecordCreate(BaseModel):
    record_id: str
    scene: str
    file_path: str
    image_url: str
    annotated_url: Optional[str] = None
    overall_risk: str
    summary: str
    items: List[RecordItem] = Field(default_factory=list)


class RecordUpdate(BaseModel):
    overall_risk: Optional[str] = None
    summary: Optional[str] = None
    items: Optional[List[RecordItem]] = None
    annotated_url: Optional[str] = None


class Record(RecordBase):
    model_config = ConfigDict(from_attributes=True)

    created_at: str

    @classmethod
    def from_orm(cls, obj):
        items: List[RecordItem] = []
        raw_items = getattr(obj, "items_json", "")
        if raw_items:
            try:
                parsed = json.loads(raw_items)
                if isinstance(parsed, list):
                    items = [RecordItem(**x) for x in parsed if isinstance(x, dict)]
            except Exception:
                items = []

        return cls(
            record_id=obj.record_id,
            scene=obj.scene,
            file_path=obj.file_path,
            image_url=obj.image_url,
            annotated_url=obj.annotated_url,
            overall_risk=obj.overall_risk,
            summary=obj.summary,
            items=items,
            created_at=obj.created_at.isoformat() if getattr(obj, "created_at", None) else "",
        )


class RecordListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    record_id: str
    created_at: str
    overall_risk: str
    summary: str
    thumbnail_url: str

    @classmethod
    def from_orm(cls, obj):
        return cls(
            record_id=obj.record_id,
            created_at=obj.created_at.isoformat() if getattr(obj, "created_at", None) else "",
            overall_risk=obj.overall_risk,
            summary=obj.summary,
            thumbnail_url=obj.image_url,
        )


class RecordListResponse(BaseModel):
    total: int
    records: List[RecordListItem]


class AnalysisResponse(BaseModel):
    record_id: str
    image_url: str
    annotated_url: Optional[str] = None
    overall_risk: str
    summary: str
    items: List[RecordItem]
    citations: List[Citation] = Field(default_factory=list)
    stage1_result: Optional[Dict[str, Any]] = None
    raw_output: Optional[str] = ""
    raw_output_stage1: Optional[str] = ""
    raw_output_stage2: Optional[str] = ""
    debug: Optional[Dict[str, Any]] = Field(default=None, alias="_debug")

    model_config = ConfigDict(populate_by_name=True)


class InsightCountItem(BaseModel):
    type: str
    count: int


class InsightSceneItem(BaseModel):
    scene: str
    count: int


class InsightWindowMetrics(BaseModel):
    total_records: int
    safe_count: int
    warning_count: int
    danger_count: int
    high_risk_ratio: float
    warning_risk_ratio: float
    top_hazards: List[InsightCountItem] = Field(default_factory=list)
    repeated_scenes: List[InsightSceneItem] = Field(default_factory=list)


class InsightTrend(BaseModel):
    delta_high_risk_ratio: float
    direction: str
    summary: str


class InsightAlert(BaseModel):
    hazard_type: str
    streak: int
    level: str


class InsightSuggestion(BaseModel):
    priority: int
    title: str
    reason: str
    steps: List[str] = Field(default_factory=list)
    expected_effect: str


class RecordInsightsResponse(BaseModel):
    generated_at: str
    days: int
    safety_score: int
    cached: bool = False
    windows: Dict[str, InsightWindowMetrics]
    trends: Dict[str, InsightTrend]
    recurrence_alerts: List[InsightAlert] = Field(default_factory=list)
    recommendation_source: str
    recommendations: List[InsightSuggestion] = Field(default_factory=list)


class RiskProfileItem(BaseModel):
    scene: str
    hazard_type: str
    count_7d: int
    count_30d: int
    last_summary: str
    updated_at: str


class MemoryTaskItem(BaseModel):
    task_id: str
    source_record_id: str = ""
    hazard_type: str
    priority: int
    status: str
    title: str
    action_plan: List[str] = Field(default_factory=list)
    updated_at: str


class SimilarCaseItem(BaseModel):
    record_id: str
    scene: str
    overall_risk: str
    summary: str
    hazards: List[str] = Field(default_factory=list)
    score: float
    created_at: str


class MemoryOverviewResponse(BaseModel):
    summary: str
    recurring_hazards: List[RiskProfileItem] = Field(default_factory=list)
    profiles: List[RiskProfileItem] = Field(default_factory=list)
    open_tasks: List[MemoryTaskItem] = Field(default_factory=list)
    similar_cases: List[SimilarCaseItem] = Field(default_factory=list)
    similar_cases_mode: str = ""
    similar_cases_signature: str = ""


class MemoryTaskListResponse(BaseModel):
    total: int
    tasks: List[MemoryTaskItem] = Field(default_factory=list)


# --------------- Core Memory + Snapshot ---------------

class CoreMemoryRuleItem(BaseModel):
    id: Optional[int] = None
    scope: str = "global"
    priority: int = 5
    text: str
    enabled: bool = True
    source: str = "seed"
    updated_at: str = ""


class CoreMemoryListResponse(BaseModel):
    scope: str
    total: int
    rules: List[CoreMemoryRuleItem] = Field(default_factory=list)


class CoreMemoryCreateRequest(BaseModel):
    scope: str = Field(default="global", max_length=40)
    text: str = Field(..., min_length=1, max_length=600)
    priority: int = Field(default=5, ge=1, le=10)


class CoreMemoryUpdateRequest(BaseModel):
    text: Optional[str] = Field(default=None, max_length=600)
    priority: Optional[int] = Field(default=None, ge=1, le=10)
    enabled: Optional[bool] = None
    scope: Optional[str] = Field(default=None, max_length=40)


class MemorySnapshotCore(BaseModel):
    scope: str
    rules: List[CoreMemoryRuleItem] = Field(default_factory=list)
    is_persisted: bool = True


class MemorySnapshotTask(BaseModel):
    session_id: str = ""
    scene: str = ""
    user_goal: str = ""
    # Thesis §5.7.2 — task_goal and planner_intent carry the Planner-derived
    # session anchor; goal_version + goal_reset_reason expose the active
    # reset semantics so the front-end inspector can render "v1→v2" badges.
    task_goal: str = ""
    planner_intent: Dict[str, Any] = Field(default_factory=dict)
    goal_version: int = 1
    goal_reset_reason: str = ""
    current_record_id: str = ""
    current_record_risk: str = ""
    current_record_summary: str = ""
    short_term_summary: str = ""
    scene_guide: Dict[str, Any] = Field(default_factory=dict)


class MemorySnapshotShortTerm(BaseModel):
    session_id: str = ""
    summary: str = ""
    recent_messages: List[Dict[str, Any]] = Field(default_factory=list)
    message_count: int = 0


class MemorySnapshotLongTerm(BaseModel):
    summary: str = ""
    profiles: List[RiskProfileItem] = Field(default_factory=list)
    recurring_hazards: List[RiskProfileItem] = Field(default_factory=list)
    open_tasks: List[MemoryTaskItem] = Field(default_factory=list)
    similar_cases: List[SimilarCaseItem] = Field(default_factory=list)
    similar_cases_mode: str = ""
    similar_cases_signature: str = ""
    index_stats: Dict[str, Any] = Field(default_factory=dict)


class MemorySnapshotStats(BaseModel):
    total_records: int = 0
    total_profiles: int = 0
    total_open_tasks: int = 0
    total_core_rules: int = 0


class MemorySnapshotResponse(BaseModel):
    generated_at: str
    session_id: str = ""
    scene: str = ""
    query: str = ""
    core: MemorySnapshotCore
    task: MemorySnapshotTask
    short_term: MemorySnapshotShortTerm
    long_term: MemorySnapshotLongTerm
    stats: MemorySnapshotStats

