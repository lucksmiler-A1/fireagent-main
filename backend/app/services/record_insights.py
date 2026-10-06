from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models


class RecordInsightsService:
    def __init__(self) -> None:
        self.base_url = settings.SILICONFLOW_BASE_URL.rstrip("/")
        self.text_model = settings.SILICONFLOW_TEXT_MODEL
        self._memo: Dict[str, Dict[str, Any]] = {}
        self._memo_ttl_seconds = 180

    @staticmethod
    def _normalize_risk(value: Any) -> str:
        mapping = {
            "safe": "safe",
            "warning": "warning",
            "danger": "danger",
            "low": "safe",
            "medium": "warning",
            "high": "danger",
            "低": "safe",
            "中": "warning",
            "高": "danger",
        }
        key = str(value or "").strip().lower()
        return mapping.get(key, "warning")

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

    def _build_metrics(self, records: List[models.Record]) -> Dict[str, Any]:
        total = len(records)
        risk_counter: Counter[str] = Counter()
        hazard_counter: Counter[str] = Counter()
        scene_counter: Counter[str] = Counter()

        for record in records:
            risk = self._normalize_risk(getattr(record, "overall_risk", "warning"))
            risk_counter[risk] += 1
            scene = str(getattr(record, "scene", "") or "unknown").strip().lower()
            scene_counter[scene] += 1

            for item in self._parse_items(getattr(record, "items_json", "")):
                hazard = str(item.get("type") or "").strip()
                if hazard:
                    hazard_counter[hazard] += 1

        safe_count = int(risk_counter.get("safe", 0))
        warning_count = int(risk_counter.get("warning", 0))
        danger_count = int(risk_counter.get("danger", 0))

        high_ratio = round((danger_count / total) * 100, 1) if total else 0.0
        warning_ratio = round((warning_count / total) * 100, 1) if total else 0.0

        top_hazards = [
            {"type": hazard, "count": int(count)}
            for hazard, count in hazard_counter.most_common(3)
        ]
        repeated_scenes = [
            {"scene": scene, "count": int(count)}
            for scene, count in scene_counter.most_common()
            if count >= 2
        ][:3]

        return {
            "total_records": total,
            "safe_count": safe_count,
            "warning_count": warning_count,
            "danger_count": danger_count,
            "high_risk_ratio": high_ratio,
            "warning_risk_ratio": warning_ratio,
            "top_hazards": top_hazards,
            "repeated_scenes": repeated_scenes,
        }

    def _build_recurrence_alerts(self, records: List[models.Record], threshold: int = 3) -> List[Dict[str, Any]]:
        if not records:
            return []

        ordered = sorted(records, key=lambda x: getattr(x, "created_at", datetime.min))
        streak: Dict[str, int] = {}
        max_streak: Dict[str, int] = {}

        for record in ordered:
            hazards = {
                str(item.get("type") or "").strip()
                for item in self._parse_items(getattr(record, "items_json", ""))
                if str(item.get("type") or "").strip()
            }

            for key in list(streak.keys()):
                if key not in hazards:
                    streak[key] = 0

            for hazard in hazards:
                streak[hazard] = streak.get(hazard, 0) + 1
                max_streak[hazard] = max(max_streak.get(hazard, 0), streak[hazard])

        alerts = [
            {"hazard_type": hazard, "streak": int(value), "level": "high"}
            for hazard, value in sorted(max_streak.items(), key=lambda x: x[1], reverse=True)
            if value >= threshold
        ]
        return alerts[:5]

    @staticmethod
    def _build_trend(current: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
        delta = round(float(current.get("high_risk_ratio", 0.0)) - float(previous.get("high_risk_ratio", 0.0)), 1)
        if abs(delta) < 1.0:
            direction = "stable"
            summary = "高风险占比基本稳定"
        elif delta < 0:
            direction = "down"
            summary = "高风险占比下降，整体在改善"
        else:
            direction = "up"
            summary = "高风险占比上升，建议优先处理复发隐患"

        return {
            "delta_high_risk_ratio": delta,
            "direction": direction,
            "summary": summary,
        }

    @staticmethod
    def _score(metrics_7d: Dict[str, Any], alert_count: int) -> int:
        high = float(metrics_7d.get("high_risk_ratio", 0.0))
        warning = float(metrics_7d.get("warning_risk_ratio", 0.0))
        penalty = high * 0.7 + warning * 0.25 + min(alert_count * 6, 20)
        score = max(0, min(100, int(round(100 - penalty))))
        return score

    def _chat_completion(self, api_key: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        payload = {
            "model": self.text_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 500,
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
                timeout=30,
            )
        except requests.RequestException as exc:
            return {"ok": False, "error": f"request_failed: {exc}", "raw": ""}

        if response.status_code >= 400:
            return {"ok": False, "error": f"provider_http_{response.status_code}", "raw": response.text[:2000]}

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return {"ok": False, "error": "no_choices", "raw": json.dumps(data, ensure_ascii=False)[:2000]}

        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            content = "\n".join(str(x) for x in content)

        return {"ok": True, "raw": str(content or "").strip()}

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any] | None:
        if not text:
            return None

        text = text.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        match = re.search(r"(\{[\s\S]*\})", text)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return None
        return None

    @staticmethod
    def _fallback_recommendations(metrics_7d: Dict[str, Any], metrics_30d: Dict[str, Any], alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        recs: List[Dict[str, Any]] = []

        high_ratio = float(metrics_7d.get("high_risk_ratio", 0.0))
        if high_ratio >= 20:
            recs.append(
                {
                    "priority": 1,
                    "title": "先处理高风险点位",
                    "reason": f"近7天高风险占比为 {high_ratio}% ，需要先降风险。",
                    "steps": ["按风险等级生成整改清单", "48小时内完成高风险点复查", "未完成项设为重点跟踪"],
                    "expected_effect": "在一周内显著降低高风险占比。",
                }
            )

        top_hazards = metrics_30d.get("top_hazards") or []
        if top_hazards:
            h = top_hazards[0]
            recs.append(
                {
                    "priority": 2,
                    "title": f"专项整治：{h.get('type', '高频隐患')}",
                    "reason": "该隐患在近30天重复出现频次最高。",
                    "steps": ["制定该隐患排查标准", "在高频场景集中排查", "形成标准化整改模板"],
                    "expected_effect": "降低同类隐患复发概率。",
                }
            )

        if alerts:
            a = alerts[0]
            recs.append(
                {
                    "priority": 3,
                    "title": "启动复发预警整改",
                    "reason": f"{a.get('hazard_type', '同类隐患')} 已连续出现 {a.get('streak', 0)} 次。",
                    "steps": ["对复发点位安排现场复盘", "指定责任人和整改时限", "连续三天复核并记录"],
                    "expected_effect": "阻断复发链，提升整改闭环率。",
                }
            )

        while len(recs) < 3:
            idx = len(recs) + 1
            recs.append(
                {
                    "priority": idx,
                    "title": "建立每周复盘机制",
                    "reason": "通过固定节奏复盘可持续降低风险。",
                    "steps": ["每周固定时间汇总新增隐患", "按场景输出Top问题", "复盘未完成项并更新计划"],
                    "expected_effect": "提升整体安全改进效率。",
                }
            )

        return recs[:3]

    def _generate_recommendations(
        self,
        metrics_7d: Dict[str, Any],
        metrics_30d: Dict[str, Any],
        trend_7d: Dict[str, Any],
        alerts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        api_key = settings.SILICONFLOW_API_KEY or os.getenv("SILICONFLOW_API_KEY")
        if not api_key:
            return {
                "source": "rule_based",
                "items": self._fallback_recommendations(metrics_7d, metrics_30d, alerts),
            }

        structured_input = {
            "metrics_7d": metrics_7d,
            "metrics_30d": metrics_30d,
            "trend_7d": trend_7d,
            "recurrence_alerts": alerts,
        }

        messages = [
            {"role": "system", "content": "你是消防安全审查员，只输出JSON，不要markdown。"},
            {
                "role": "user",
                "content": (
                    "基于以下结构化统计数据，输出3条按优先级排序的整改建议。"
                    "每条需包含: priority(1-3), title, reason, steps(数组,3步), expected_effect。"
                    "返回JSON格式: {\"suggestions\":[...]}。\n\n"
                    f"DATA:\n{json.dumps(structured_input, ensure_ascii=False)}"
                ),
            },
        ]

        llm = self._chat_completion(api_key, messages)
        if not llm.get("ok"):
            return {
                "source": "rule_based",
                "items": self._fallback_recommendations(metrics_7d, metrics_30d, alerts),
            }

        parsed = self._extract_json(str(llm.get("raw", ""))) or {}
        suggestions = parsed.get("suggestions") if isinstance(parsed, dict) else None

        cleaned: List[Dict[str, Any]] = []
        if isinstance(suggestions, list):
            for i, item in enumerate(suggestions[:3], start=1):
                if not isinstance(item, dict):
                    continue
                steps = item.get("steps") if isinstance(item.get("steps"), list) else []
                clean_steps = [str(x).strip() for x in steps if str(x).strip()][:3]
                if len(clean_steps) < 3:
                    clean_steps = (clean_steps + ["执行现场复核", "落实整改措施", "复查并记录结果"])[:3]
                cleaned.append(
                    {
                        "priority": int(item.get("priority", i) or i),
                        "title": str(item.get("title") or f"整改建议{i}").strip(),
                        "reason": str(item.get("reason") or "基于历史统计生成").strip(),
                        "steps": clean_steps,
                        "expected_effect": str(item.get("expected_effect") or "降低隐患风险").strip(),
                    }
                )

        if len(cleaned) < 3:
            return {
                "source": "rule_based",
                "items": self._fallback_recommendations(metrics_7d, metrics_30d, alerts),
            }

        cleaned = sorted(cleaned, key=lambda x: x.get("priority", 99))[:3]
        for idx, item in enumerate(cleaned, start=1):
            item["priority"] = idx

        return {"source": "llm", "items": cleaned}

    def build_insights(self, db: Session, days: int = 7) -> Dict[str, Any]:
        now = datetime.utcnow()
        days = max(3, min(int(days), 30))

        records = (
            db.query(models.Record)
            .order_by(models.Record.created_at.desc())
            .limit(3000)
            .all()
        )

        latest = records[0] if records else None
        signature = {
            "days": days,
            "count": len(records),
            "latest_id": getattr(latest, "record_id", ""),
            "latest_ts": getattr(latest, "created_at", datetime.min).isoformat() if latest else "",
        }
        memo_key = f"insights_{days}"
        memo = self._memo.get(memo_key)
        if memo:
            age = (now - memo.get("time", datetime.min)).total_seconds()
            if age < self._memo_ttl_seconds and memo.get("signature") == signature:
                cached = dict(memo.get("data") or {})
                cached["cached"] = True
                return cached

        def in_window(start: datetime, end: datetime) -> List[models.Record]:
            return [r for r in records if start <= getattr(r, "created_at", datetime.min) < end]

        cur_7 = in_window(now - timedelta(days=7), now)
        prev_7 = in_window(now - timedelta(days=14), now - timedelta(days=7))
        cur_30 = in_window(now - timedelta(days=30), now)
        prev_30 = in_window(now - timedelta(days=60), now - timedelta(days=30))

        metrics_7d = self._build_metrics(cur_7)
        metrics_30d = self._build_metrics(cur_30)
        trend_7d = self._build_trend(metrics_7d, self._build_metrics(prev_7))
        trend_30d = self._build_trend(metrics_30d, self._build_metrics(prev_30))
        alerts = self._build_recurrence_alerts(cur_30, threshold=3)

        rec_bundle = self._generate_recommendations(metrics_7d, metrics_30d, trend_7d, alerts)
        safety_score = self._score(metrics_7d, len(alerts))

        result = {
            "generated_at": now.isoformat(),
            "days": days,
            "safety_score": safety_score,
            "windows": {
                "7d": metrics_7d,
                "30d": metrics_30d,
            },
            "trends": {
                "7d": trend_7d,
                "30d": trend_30d,
            },
            "recurrence_alerts": alerts,
            "recommendation_source": rec_bundle.get("source", "rule_based"),
            "recommendations": rec_bundle.get("items", []),
            "cached": False,
        }
        self._memo[memo_key] = {
            "time": now,
            "signature": signature,
            "data": result,
        }
        return result


record_insights_service = RecordInsightsService()
