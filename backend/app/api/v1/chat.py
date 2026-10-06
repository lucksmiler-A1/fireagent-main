"""
OpenAI-compatible chat completion proxy for SiliconFlow.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Optional, Union

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, conint, confloat

router = APIRouter()

SILICONFLOW_URL = "https://api.siliconflow.cn/v1/chat/completions"
DEFAULT_MODEL = "Qwen/Qwen3.6-35B-A3B"


class MessageContentPart(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[Dict[str, str]] = None


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, List[MessageContentPart]]
    name: Optional[str] = None


class ResponseFormat(BaseModel):
    type: Literal["text", "json_object"] = "text"


class ChatCompletionRequest(BaseModel):
    model: str = Field(default=DEFAULT_MODEL, description="Model name")
    messages: List[ChatMessage] = Field(..., min_length=1, max_length=10)
    stream: Optional[bool] = False
    max_tokens: Optional[int] = None
    enable_thinking: Optional[bool] = None
    thinking_budget: Optional[conint(ge=128, le=32768)] = 4096
    min_p: Optional[confloat(ge=0, le=1)] = None
    stop: Optional[Union[str, List[str]]] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[float] = None
    frequency_penalty: Optional[float] = None
    n: Optional[int] = 1
    response_format: Optional[ResponseFormat] = None
    tools: Optional[List[Dict[str, Any]]] = None


@router.post("/completions")
def create_chat_completion(payload: ChatCompletionRequest):
    """
    Proxy request to SiliconFlow OpenAI-compatible chat completions API.
    """
    if payload.stream:
        raise HTTPException(status_code=400, detail="stream=true is not supported by this proxy endpoint.")

    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="SILICONFLOW_API_KEY is not configured.")

    body: Dict[str, Any] = payload.model_dump(exclude_none=True)
    body["model"] = body.get("model") or DEFAULT_MODEL
    if body["model"] == DEFAULT_MODEL and "enable_thinking" not in body:
        body["enable_thinking"] = False

    try:
        response = requests.post(
            SILICONFLOW_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=120,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Failed to reach SiliconFlow: {exc}") from exc

    if response.status_code >= 400:
        detail: Union[str, Dict[str, Any]]
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    trace_id = response.headers.get("x-siliconcloud-trace-id", "")
    data = response.json()
    if trace_id:
        data["x_siliconcloud_trace_id"] = trace_id
    return data
