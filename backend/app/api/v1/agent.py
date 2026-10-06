from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.agent import agent_service

router = APIRouter()


class AgentHistoryMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str = Field(..., min_length=1, max_length=600)


class AgentCurrentRecordItem(BaseModel):
    type: str = Field(default="", max_length=120)
    risk: str = Field(default="", max_length=40)
    desc: str = Field(default="", max_length=400)
    suggest: str = Field(default="", max_length=400)


class AgentCurrentRecord(BaseModel):
    record_id: str = Field(..., min_length=1, max_length=60)
    scene: str = Field(default="campus", max_length=40)
    overall_risk: str = Field(default="warning", max_length=40)
    summary: str = Field(default="", max_length=1000)
    items: List[AgentCurrentRecordItem] = Field(default_factory=list)
    citations: List[dict] = Field(default_factory=list)


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    scene: str = Field(default="campus", max_length=40)
    session_id: Optional[str] = Field(default=None, max_length=60)
    history: List[AgentHistoryMessage] = Field(default_factory=list)
    current_record: Optional[AgentCurrentRecord] = None


class AgentCitation(BaseModel):
    article: str
    source: str
    quote: str


class AgentChatResponse(BaseModel):
    session_id: str
    reply: str
    next_actions: List[str] = Field(default_factory=list)
    citations: List[AgentCitation] = Field(default_factory=list)
    used_tools: List[str] = Field(default_factory=list)
    confidence: str = "medium"
    memory: Optional[dict] = None
    plan: Optional[dict] = None
    tool_outputs: Optional[dict] = None


@router.post("/chat", response_model=AgentChatResponse)
def chat_with_agent(payload: AgentChatRequest, db: Session = Depends(get_db)):
    return agent_service.chat(
        db=db,
        message=payload.message,
        scene=payload.scene,
        session_id=payload.session_id,
        history_messages=[item.model_dump() for item in payload.history],
        current_record=payload.current_record.model_dump() if payload.current_record else None,
    )
