from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import crud
from app.services.memory import memory_manager
from app.services.production_safety import production_safety_service
from app.services.record_insights import record_insights_service
from app.services.retriever import rule_retriever


class AgentService:
    def __init__(self) -> None:
        self.base_url = settings.SILICONFLOW_BASE_URL.rstrip("/")
        self.text_model = settings.SILICONFLOW_TEXT_MODEL

    @staticmethod
    def _safe_text(value: Any, max_len: int = 2000) -> str:
        return str(value or "").strip()[:max_len]

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any] | None:
        if not text:
            return None

        raw = str(text).strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        fence_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", raw, re.IGNORECASE)
        if fence_match:
            try:
                parsed = json.loads(fence_match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        obj_match = re.search(r"(\{[\s\S]*\})", raw)
        if obj_match:
            try:
                parsed = json.loads(obj_match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return None
        return None

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
    def _generate_session_id() -> str:
        return f"s_{uuid.uuid4().hex[:12]}"

    def _chat_completion(
        self,
        api_key: str,
        messages: List[Dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 900,
    ) -> Dict[str, Any]:
        payload = {
            "model": self.text_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "enable_thinking": False,
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
        except requests.RequestException as exc:
            return {"ok": False, "error": f"request_failed: {exc}", "raw": ""}

        if response.status_code >= 400:
            return {
                "ok": False,
                "error": f"provider_http_{response.status_code}",
                "raw": response.text[:4000],
            }

        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            return {"ok": False, "error": "no_choices", "raw": json.dumps(body, ensure_ascii=False)[:4000]}

        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            content = "\n".join(str(x) for x in content)
        return {"ok": True, "raw": str(content or "").strip()}

    def _heuristic_plan(self, message: str, scene: str) -> Dict[str, Any]:
        text = str(message or "").strip()
        lowered = text.lower()
        scene_lower = str(scene or "").strip().lower()

        rule_keywords = [
            "法规",
            "法条",
            "条款",
            "规范",
            "依据",
            "要求",
            "标准",
            "合规",
            "消防法",
            "能不能",
            "是否可以",
        ]
        history_keywords = [
            "历史",
            "记录",
            "最近",
            "过去",
            "之前",
            "复发",
            "整改",
            "出现过",
            "高风险",
            "隐患",
            "主要是什么",
            "top",
        ]
        insight_keywords = [
            "趋势",
            "统计",
            "分析",
            "建议",
            "改进",
            "评分",
            "高风险占比",
            "复盘",
            "总结",
        ]

        production_keywords = [
            "工地",
            "施工",
            "生产安全",
            "安全生产",
            "临时用电",
            "配电箱",
            "开关箱",
            "动火",
            "电焊",
            "吊装",
            "高处作业",
            "脚手架",
            "有限空间",
            "受限空间",
            "ppe",
            "temporary power",
            "hot work",
            "scaffold",
            "lifting",
            "confined space",
            "industrial safety",
        ]

        needs_rules = any(word in text for word in rule_keywords)
        needs_history = any(word in text for word in history_keywords)
        needs_insights = any(word in text for word in insight_keywords)
        needs_production_safety = scene_lower in {"construction", "industrial"} or any(
            (word in lowered) or (word in text) for word in production_keywords
        )

        if not (needs_rules or needs_history or needs_insights or needs_production_safety):
            needs_rules = True

        response_style = "concise"
        if any(word in text for word in ["步骤", "怎么做", "如何", "清单", "方案", "整改"]):
            response_style = "actionable"
        elif any(word in text for word in ["详细", "展开", "全面", "完整"]):
            response_style = "detailed"

        record_ids = re.findall(r"\br_[0-9a-z]{6,16}\b", lowered)

        return {
            "goal": text[:120] or "回答消防安全问题",
            "scene": scene,
            "needs_rules": needs_rules,
            "needs_history": needs_history or bool(record_ids),
            "needs_insights": needs_insights,
            "needs_production_safety": needs_production_safety,
            "needs_record_detail": bool(record_ids),
            "record_id": record_ids[0] if record_ids else "",
            "rule_query": text[:500],
            "max_records": 5 if (needs_history or record_ids) else 0,
            "insight_days": 7 if needs_insights else 0,
            "response_style": response_style,
        }

    def _plan(self, api_key: Optional[str], message: str, scene: str) -> Dict[str, Any]:
        fallback = self._heuristic_plan(message, scene)
        if not api_key:
            return fallback

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a planning module for a fire-safety agent."
                    " Return JSON only. Do not use markdown and do not explain."
                    " Prefer evidence-driven planning and avoid unnecessary tool calls."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Decide which tools are needed for the user question."
                    " Available tools: rules(legal retrieval), history(history records), insights(trend insights),"
                    " record_detail(single record detail), long_term_memory(experience memory retrieval),"
                    " production_safety(construction/industrial safety guidance)."
                    " Return JSON: "
                    "{\"goal\":\"...\",\"scene\":\"campus\",\"needs_rules\":true,\"needs_history\":false,"
                    "\"needs_insights\":false,\"needs_production_safety\":false,"
                    "\"needs_record_detail\":false,\"record_id\":\"\","
                    "\"rule_query\":\"...\",\"max_records\":5,\"insight_days\":7,"
                    "\"response_style\":\"concise|actionable|detailed\"}\n\n"
                    f"SCENE: {scene}\n"
                    f"QUESTION: {message}"
                ),
            },
        ]

        result = self._chat_completion(api_key, messages, temperature=0.1, max_tokens=260)
        if not result.get("ok"):
            return fallback

        parsed = self._extract_json(str(result.get("raw", "")))
        if not isinstance(parsed, dict):
            return fallback

        plan = {
            "goal": self._safe_text(parsed.get("goal"), 120) or fallback["goal"],
            "scene": scene,
            "needs_rules": bool(parsed.get("needs_rules")),
            "needs_history": bool(parsed.get("needs_history")),
            "needs_insights": bool(parsed.get("needs_insights")),
            "needs_production_safety": bool(parsed.get("needs_production_safety")),
            "needs_record_detail": bool(parsed.get("needs_record_detail")),
            "record_id": self._safe_text(parsed.get("record_id"), 40),
            "rule_query": self._safe_text(parsed.get("rule_query"), 500) or fallback["rule_query"],
            "max_records": max(0, min(int(parsed.get("max_records") or fallback["max_records"]), 10)),
            "insight_days": max(0, min(int(parsed.get("insight_days") or fallback["insight_days"]), 30)),
            "response_style": self._safe_text(parsed.get("response_style"), 20) or fallback["response_style"],
        }

        if not (
            plan["needs_rules"]
            or plan["needs_history"]
            or plan["needs_insights"]
            or plan["needs_production_safety"]
            or plan["needs_record_detail"]
        ):
            return fallback
        if plan["needs_record_detail"] and not plan["record_id"]:
            plan["needs_record_detail"] = False
        if fallback["needs_history"]:
            plan["needs_history"] = True
            plan["max_records"] = max(plan["max_records"], fallback["max_records"])
        if fallback["needs_insights"]:
            plan["needs_insights"] = True
            plan["insight_days"] = max(plan["insight_days"], fallback["insight_days"])
        if fallback.get("needs_production_safety"):
            plan["needs_production_safety"] = True
        if fallback["needs_rules"] and any(word in message for word in ["法规", "法条", "条款", "规范", "依据"]):
            plan["needs_rules"] = True

        return plan

    def _build_rules_context(self, query: str, scene: str) -> Dict[str, Any]:
        retrieval = rule_retriever.retrieve_with_debug(
            query=query,
            scene=scene,
            top_k=min(max(settings.RAG_TOP_K, 3), 5),
            min_score=settings.RAG_MIN_SCORE,
            min_token_hits=settings.RAG_MIN_TOKEN_HITS,
        )
        rules = retrieval.get("rules", [])
        return {
            "count": len(rules),
            "rules": rules,
            "debug": retrieval.get("debug", {}),
        }

    @staticmethod
    def _contains_cjk(text: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", str(text or "")))

    def _compose_rule_query(self, original_message: str, planned_query: str) -> str:
        raw_message = self._safe_text(original_message, 500)
        raw_plan = self._safe_text(planned_query, 500)
        if not raw_plan or raw_plan == raw_message:
            return raw_message
        if self._contains_cjk(raw_message) and not self._contains_cjk(raw_plan):
            return f"{raw_message}\n{raw_plan}"
        return f"{raw_message}\n{raw_plan}"

    def _build_history_context(self, db: Session, limit: int) -> Dict[str, Any]:
        rows = crud.get_records_with_limit_offset(db, limit=max(1, min(limit, 10)), offset=0)
        records: List[Dict[str, Any]] = []
        risk_counter = {"safe": 0, "warning": 0, "danger": 0}

        for row in rows:
            risk = self._safe_text(getattr(row, "overall_risk", "warning"), 20) or "warning"
            risk_counter[risk] = risk_counter.get(risk, 0) + 1
            items = self._parse_items(getattr(row, "items_json", ""))
            records.append(
                {
                    "record_id": getattr(row, "record_id", ""),
                    "created_at": getattr(row, "created_at", None).isoformat() if getattr(row, "created_at", None) else "",
                    "scene": getattr(row, "scene", ""),
                    "overall_risk": risk,
                    "summary": self._safe_text(getattr(row, "summary", ""), 240),
                    "hazards": [self._safe_text(item.get("type"), 80) for item in items[:3]],
                }
            )

        return {
            "count": len(records),
            "risk_counter": risk_counter,
            "records": records,
        }

    def _build_record_detail_context(self, db: Session, record_id: str) -> Dict[str, Any]:
        row = crud.get_record(db, record_id)
        if not row:
            return {"found": False, "record_id": record_id}
        items = self._parse_items(getattr(row, "items_json", ""))
        return {
            "found": True,
            "record": {
                "record_id": getattr(row, "record_id", ""),
                "created_at": getattr(row, "created_at", None).isoformat() if getattr(row, "created_at", None) else "",
                "scene": getattr(row, "scene", ""),
                "overall_risk": getattr(row, "overall_risk", ""),
                "summary": self._safe_text(getattr(row, "summary", ""), 800),
                "items": items[:8],
            },
        }

    def _normalize_current_record_context(self, current_record: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not isinstance(current_record, dict):
            return None
        record_id = self._safe_text(current_record.get("record_id"), 60)
        if not record_id:
            return None

        items: List[Dict[str, Any]] = []
        for item in current_record.get("items") or []:
            if not isinstance(item, dict):
                continue
            items.append(
                {
                    "type": self._safe_text(item.get("type"), 120),
                    "risk": self._safe_text(item.get("risk"), 40),
                    "desc": self._safe_text(item.get("desc"), 400),
                    "suggest": self._safe_text(item.get("suggest"), 400),
                }
            )

        citations: List[Dict[str, str]] = []
        for item in current_record.get("citations") or []:
            if not isinstance(item, dict):
                continue
            citations.append(
                {
                    "article": self._safe_text(item.get("article"), 80),
                    "source": self._safe_text(item.get("source"), 120),
                    "quote": self._safe_text(item.get("quote"), 220),
                }
            )

        return {
            "found": True,
            "record": {
                "record_id": record_id,
                "scene": self._safe_text(current_record.get("scene"), 40),
                "overall_risk": self._safe_text(current_record.get("overall_risk"), 40),
                "summary": self._safe_text(current_record.get("summary"), 800),
                "items": items[:8],
                "citations": citations[:4],
                "source": "current_record",
            },
        }

    def _build_fallback_reply(
        self,
        *,
        message: str,
        plan: Dict[str, Any],
        rules_context: Optional[Dict[str, Any]],
        history_context: Optional[Dict[str, Any]],
        insights_context: Optional[Dict[str, Any]],
        production_safety_context: Optional[Dict[str, Any]],
        record_detail_context: Optional[Dict[str, Any]],
        current_record_context: Optional[Dict[str, Any]],
        long_term_memory: Optional[Dict[str, Any]],
        used_tools: List[str],
    ) -> Dict[str, Any]:
        lines: List[str] = [f"Question: {self._safe_text(message, 200)}"]

        if current_record_context and current_record_context.get("found"):
            record = current_record_context.get("record") or {}
            lines.append(
                f"Current record: {record.get('record_id', '')}, "
                f"risk {self._safe_text(record.get('overall_risk'), 40)}, "
                f"{self._safe_text(record.get('summary'), 160)}"
            )

        if rules_context and rules_context.get("rules"):
            top_rule = rules_context["rules"][0]
            lines.append(
                "Rule evidence: "
                f"{self._safe_text(top_rule.get('source'), 80)} "
                f"{self._safe_text(top_rule.get('article'), 40)}, "
                f"{self._safe_text(top_rule.get('text'), 120)}"
            )

        if history_context and history_context.get("count"):
            danger_count = int((history_context.get("risk_counter") or {}).get("danger", 0))
            lines.append(f"History: {history_context.get('count', 0)} records, high-risk {danger_count}.")

        if insights_context and insights_context.get("windows"):
            score = insights_context.get("safety_score", 0)
            trend = ((insights_context.get("trends") or {}).get("7d") or {}).get("summary", "")
            lines.append(f"Trend insight: safety score {score}. {self._safe_text(trend, 80)}")

        if production_safety_context and production_safety_context.get("count"):
            topics = production_safety_context.get("topics") or []
            if topics:
                top_topic = topics[0]
                lines.append(
                    "Production safety focus: "
                    f"{self._safe_text(top_topic.get('title'), 120)} "
                    f"({self._safe_text(top_topic.get('domain'), 40)})."
                )

        if long_term_memory:
            summary = self._safe_text(long_term_memory.get("summary"), 180)
            if summary:
                lines.append(f"Long-term memory: {summary}")
            if long_term_memory.get("similar_cases"):
                lines.append("Similar past cases were found and can be used for remediation planning.")

        if record_detail_context and record_detail_context.get("found"):
            record = record_detail_context.get("record") or {}
            lines.append(f"Record {record.get('record_id', '')}: {self._safe_text(record.get('summary'), 120)}")

        citations: List[Dict[str, str]] = []
        if rules_context:
            for rule in (rules_context.get("rules") or [])[:3]:
                citations.append(
                    {
                        "article": self._safe_text(rule.get("article"), 80),
                        "source": self._safe_text(rule.get("source"), 120),
                        "quote": self._safe_text(rule.get("text"), 220),
                    }
                )

        return {
            "reply": "\n".join(lines),
            "next_actions": [
                "I can expand this into a remediation checklist if needed.",
                "You can ask to list open long-term remediation tasks.",
            ],
            "citations": citations,
            "used_tools": used_tools,
            "confidence": "medium",
            "plan": plan,
            "tool_outputs": {
                "rules": rules_context,
                "history": history_context,
                "insights": insights_context,
                "production_safety": production_safety_context,
                "record_detail": record_detail_context,
                "current_record": current_record_context,
                "long_term_memory": long_term_memory,
            },
        }

    def _finalize_fallback(
        self,
        *,
        db: Session,
        session_id: str,
        scene: str,
        user_message: str,
        short_term_memory: Dict[str, Any],
        task_context: Dict[str, Any],
        long_term_memory: Dict[str, Any],
        current_record_context: Optional[Dict[str, Any]],
        rules_context: Optional[Dict[str, Any]],
        fallback: Dict[str, Any],
        used_tools: List[str],
    ) -> Dict[str, Any]:
        guardrail_result = memory_manager.apply_guardrails(
            question=user_message,
            reply=fallback.get("reply", ""),
            rules_context=rules_context,
            citations=fallback.get("citations", []),
        )
        rules_query_meta = self._safe_text((rules_context or {}).get("query"), 600) if rules_context else ""
        evidence_ids_meta = [
            self._safe_text(rule.get("id"), 80)
            for rule in (rules_context or {}).get("rules", [])
            if isinstance(rule, dict) and self._safe_text(rule.get("id"), 80)
        ][:8]
        guardrail_meta = {
            "asked_for_rules": any(w in user_message for w in ["法规", "依据", "条款", "规范", "消防法", "处罚"]),
            "has_rule_evidence": bool(rules_context and rules_context.get("rules")),
            "kept_citations": len(guardrail_result.get("citations") or []),
            "branch": "fallback",
        }
        updated_summary = memory_manager.persist_short_term_memory(
            db,
            session_id=session_id,
            scene=scene,
            user_message=user_message,
            assistant_reply=guardrail_result["reply"],
            short_term_memory=short_term_memory,
            current_record_context=current_record_context,
            used_tools=used_tools,
            citations=guardrail_result["citations"],
            rules_query=rules_query_meta,
            evidence_ids=evidence_ids_meta,
            guardrail=guardrail_meta,
        )
        fallback["session_id"] = session_id
        fallback["reply"] = guardrail_result["reply"]
        fallback["citations"] = guardrail_result["citations"]
        fallback["memory"] = memory_manager.build_payload(
            task_context=task_context,
            short_term_memory=short_term_memory,
            long_term_memory=long_term_memory,
            summary=updated_summary,
            db=db,
            scene=scene,
        )
        return fallback

    def chat(
        self,
        *,
        db: Session,
        message: str,
        scene: str = "campus",
        session_id: Optional[str] = None,
        history_messages: Optional[List[Dict[str, str]]] = None,
        current_record: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        user_message = self._safe_text(message, 2000)
        scene = self._safe_text(scene, 40) or "campus"
        session_id = self._safe_text(session_id, 60) or self._generate_session_id()
        history_messages = history_messages or []
        current_record_context = self._normalize_current_record_context(current_record)

        # Plan first so the resulting intent can drive Task Memory state
        # (Task Memory is generated by the Planner and reset
        # when scene or goal changes).
        api_key = settings.SILICONFLOW_API_KEY or os.getenv("SILICONFLOW_API_KEY")
        plan = self._plan(api_key, user_message, scene)

        short_term_memory = memory_manager.load_short_term_memory(
            db,
            session_id=session_id,
            scene=scene,
            history_messages=history_messages,
            current_record_context=current_record_context,
        )
        task_context = memory_manager.build_task_context(
            session_id=session_id,
            scene=scene,
            user_message=user_message,
            current_record_context=current_record_context,
            short_term_memory=short_term_memory,
            db=db,
            planner_intent=plan,
        )
        long_term_memory = memory_manager.build_long_term_context(db, query=user_message, scene=scene)

        used_tools: List[str] = []
        rules_context: Optional[Dict[str, Any]] = None
        history_context: Optional[Dict[str, Any]] = None
        insights_context: Optional[Dict[str, Any]] = None
        production_safety_context: Optional[Dict[str, Any]] = None
        record_detail_context: Optional[Dict[str, Any]] = None

        if current_record_context and current_record_context.get("found"):
            used_tools.append("current_record")
        if long_term_memory and (
            long_term_memory.get("profiles") or long_term_memory.get("similar_cases") or long_term_memory.get("open_tasks")
        ):
            used_tools.append("long_term_memory")

        if plan.get("needs_rules"):
            used_tools.append("rules")
            rules_query = self._compose_rule_query(user_message, plan.get("rule_query") or "")
            if current_record_context and current_record_context.get("found"):
                record = current_record_context.get("record") or {}
                summary = self._safe_text(record.get("summary"), 220)
                item_types = " ".join(
                    self._safe_text(item.get("type"), 60)
                    for item in (record.get("items") or [])[:4]
                    if isinstance(item, dict)
                )
                if summary or item_types:
                    rules_query = f"{rules_query}\n{summary}\n{item_types}".strip()
            rules_context = self._build_rules_context(rules_query, scene)

        if plan.get("needs_history"):
            used_tools.append("history")
            history_context = self._build_history_context(db, plan.get("max_records") or 5)

        if plan.get("needs_insights"):
            used_tools.append("insights")
            days = max(3, min(int(plan.get("insight_days") or 7), 30))
            insights_context = record_insights_service.build_insights(db, days=days)

        if plan.get("needs_production_safety"):
            used_tools.append("production_safety")
            production_safety_context = production_safety_service.build_context(
                scene=scene,
                message=user_message,
            )

        if plan.get("needs_record_detail") and plan.get("record_id"):
            used_tools.append("record_detail")
            record_detail_context = self._build_record_detail_context(db, plan["record_id"])

        recent_chat = []
        for item in short_term_memory.get("recent_messages", [])[-6:]:
            role = "assistant" if str(item.get("role")) == "assistant" else "user"
            content = self._safe_text(item.get("content"), 600)
            if content:
                recent_chat.append({"role": role, "content": content})

        fallback_payload = self._build_fallback_reply(
            message=user_message,
            plan=plan,
            rules_context=rules_context,
            history_context=history_context,
            insights_context=insights_context,
            production_safety_context=production_safety_context,
            record_detail_context=record_detail_context,
            current_record_context=current_record_context,
            long_term_memory=long_term_memory,
            used_tools=used_tools,
        )

        if not api_key:
            return self._finalize_fallback(
                db=db,
                session_id=session_id,
                scene=scene,
                user_message=user_message,
                short_term_memory=short_term_memory,
                task_context=task_context,
                long_term_memory=long_term_memory,
                current_record_context=current_record_context,
                rules_context=rules_context,
                fallback=fallback_payload,
                used_tools=used_tools,
            )

        system_prompt = (
            "You are the built-in fire-safety agent for this project."
            " Answer using the provided retrieval results, production safety context, history, trend context, and long-term memory only."
            " Do not invent legal evidence, and omit citations when no rule evidence is available."
            " If evidence is insufficient, say so clearly."
            f" Core rules: {'; '.join(memory_manager.core_rules(db=db, scene=scene))}"
            " Return JSON only."
        )

        final_payload = {
            "question": user_message,
            "scene": scene,
            "plan": plan,
            "task_context": task_context,
            "short_term_memory": short_term_memory,
            "long_term_memory": long_term_memory,
            "recent_chat": recent_chat,
            "current_record_context": current_record_context,
            "rules_context": rules_context,
            "history_context": history_context,
            "insights_context": insights_context,
            "production_safety_context": production_safety_context,
            "record_detail_context": record_detail_context,
        }

        final_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Based on the tool outputs below, return JSON only: "
                    "{\"reply\":\"\",\"next_actions\":[\"\"],\"citations\":[{\"article\":\"\",\"source\":\"\",\"quote\":\"\"}],"
                    "\"used_tools\":[\"rules\"],\"confidence\":\"high|medium|low\"}\n\n"
                    f"DATA:\n{json.dumps(final_payload, ensure_ascii=False)}"
                ),
            },
        ]

        llm = self._chat_completion(api_key, final_messages, temperature=0.25, max_tokens=1100)
        if not llm.get("ok"):
            return self._finalize_fallback(
                db=db,
                session_id=session_id,
                scene=scene,
                user_message=user_message,
                short_term_memory=short_term_memory,
                task_context=task_context,
                long_term_memory=long_term_memory,
                current_record_context=current_record_context,
                rules_context=rules_context,
                fallback=fallback_payload,
                used_tools=used_tools,
            )

        parsed = self._extract_json(str(llm.get("raw", "")))
        if not isinstance(parsed, dict):
            return self._finalize_fallback(
                db=db,
                session_id=session_id,
                scene=scene,
                user_message=user_message,
                short_term_memory=short_term_memory,
                task_context=task_context,
                long_term_memory=long_term_memory,
                current_record_context=current_record_context,
                rules_context=rules_context,
                fallback=fallback_payload,
                used_tools=used_tools,
            )

        citations: List[Dict[str, str]] = []
        if rules_context and (rules_context.get("rules") or []):
            allowed_pairs = {
                (str(rule.get("article", "")), str(rule.get("source", "")))
                for rule in rules_context.get("rules", [])
            }
            for item in parsed.get("citations") or []:
                if not isinstance(item, dict):
                    continue
                article = self._safe_text(item.get("article"), 80)
                source = self._safe_text(item.get("source"), 120)
                if (article, source) not in allowed_pairs:
                    continue
                citations.append(
                    {
                        "article": article,
                        "source": source,
                        "quote": self._safe_text(item.get("quote"), 220),
                    }
                )
            if not citations:
                for rule in (rules_context.get("rules") or [])[:3]:
                    citations.append(
                        {
                            "article": self._safe_text(rule.get("article"), 80),
                            "source": self._safe_text(rule.get("source"), 120),
                            "quote": self._safe_text(rule.get("text"), 220),
                        }
                    )

        next_actions = []
        for action in parsed.get("next_actions") or []:
            clean = self._safe_text(action, 120)
            if clean:
                next_actions.append(clean)

        used_tools_output = [
            self._safe_text(x, 30)
            for x in (parsed.get("used_tools") or used_tools)
            if self._safe_text(x, 30)
        ]

        reply_text = self._safe_text(parsed.get("reply"), 4000) or fallback_payload["reply"]
        guardrail_result = memory_manager.apply_guardrails(
            question=user_message,
            reply=reply_text,
            rules_context=rules_context,
            citations=citations[:4],
        )
        # Thesis §5.7.3: persist structured retrieval/guardrail metadata so
        # downstream audits work on fields, not raw log text.
        rules_query_meta = self._safe_text((rules_context or {}).get("query"), 600) if rules_context else ""
        evidence_ids_meta = [
            self._safe_text(rule.get("id"), 80)
            for rule in (rules_context or {}).get("rules", [])
            if isinstance(rule, dict) and self._safe_text(rule.get("id"), 80)
        ][:8]
        guardrail_meta = {
            "asked_for_rules": any(w in user_message for w in ["法规", "依据", "条款", "规范", "消防法", "处罚"]),
            "has_rule_evidence": bool(rules_context and rules_context.get("rules")),
            "kept_citations": len(guardrail_result.get("citations") or []),
            "confidence": self._safe_text(parsed.get("confidence"), 10) or "medium",
        }
        updated_summary = memory_manager.persist_short_term_memory(
            db,
            session_id=session_id,
            scene=scene,
            user_message=user_message,
            assistant_reply=guardrail_result["reply"],
            short_term_memory=short_term_memory,
            current_record_context=current_record_context,
            used_tools=used_tools_output,
            citations=guardrail_result["citations"],
            rules_query=rules_query_meta,
            evidence_ids=evidence_ids_meta,
            guardrail=guardrail_meta,
        )

        return {
            "session_id": session_id,
            "reply": guardrail_result["reply"],
            "next_actions": next_actions[:4],
            "citations": guardrail_result["citations"][:4],
            "used_tools": used_tools_output,
            "confidence": self._safe_text(parsed.get("confidence"), 10) or "medium",
            "memory": memory_manager.build_payload(
                task_context=task_context,
                short_term_memory=short_term_memory,
                long_term_memory=long_term_memory,
                summary=updated_summary,
                db=db,
                scene=scene,
            ),
            "plan": plan,
            "tool_outputs": {
                "rules": rules_context,
                "history": history_context,
                "insights": insights_context,
                "production_safety": production_safety_context,
                "record_detail": record_detail_context,
                "current_record": current_record_context,
                "long_term_memory": long_term_memory,
                "task_context": task_context,
            },
        }


agent_service = AgentService()
