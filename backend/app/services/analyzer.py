from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List

import requests

from app.core.config import settings
from app.services.result_cache import result_cache_service
from app.services.retriever import rule_retriever


class AnalyzerService:
    def __init__(self):
        self.base_url = settings.SILICONFLOW_BASE_URL.rstrip("/")
        self.vision_model = settings.SILICONFLOW_VISION_MODEL
        self.text_model = settings.SILICONFLOW_TEXT_MODEL

    @staticmethod
    def generate_record_id() -> str:
        return f"r_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _encode_image_to_data_url(image_path: str) -> str:
        mime_type, _ = mimetypes.guess_type(image_path)
        mime_type = mime_type or "image/jpeg"
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{b64}"

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

        fence_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
        if fence_match:
            try:
                parsed = json.loads(fence_match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        obj_match = re.search(r"(\{[\s\S]*\})", text)
        if obj_match:
            try:
                parsed = json.loads(obj_match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return None

        return None

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
    def _safe_text(value: Any, max_len: int = 1200) -> str:
        return str(value or "").strip()[:max_len]

    @staticmethod
    def _is_cacheable_result(result: Dict[str, Any]) -> bool:
        debug = result.get("_debug") if isinstance(result, dict) else None
        status = str((debug or {}).get("status", "")).strip().lower()
        return status in {"success", "guarded"}

    def _finalize_with_cache(
        self,
        result: Dict[str, Any],
        *,
        scene: str,
        image_hash: str,
        cache_hit: bool,
        forced: bool = False,
    ) -> Dict[str, Any]:
        if not isinstance(result, dict):
            return result

        cache_available = bool(image_hash)
        debug = result.setdefault("_debug", {})
        debug["cache"] = {
            "enabled": settings.RESULT_CACHE_ENABLED and cache_available,
            "backend": "local_file",
            "hit": cache_hit,
            "forced": forced,
            "scene": result_cache_service.normalize_scene(scene),
            "image_hash_prefix": image_hash[:16],
            "ttl_seconds": settings.RESULT_CACHE_TTL_SECONDS,
        }

        if cache_available and (not cache_hit) and self._is_cacheable_result(result):
            result_cache_service.set(scene=scene, image_hash=image_hash, data=result)

        return result

    def _chat_completion(self, api_key: str, model: str, messages: List[Dict[str, Any]], temperature: float, max_tokens: int) -> Dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if model == self.text_model:
            payload["enable_thinking"] = False

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=300,
            )
        except requests.RequestException as exc:
            return {
                "ok": False,
                "trace_id": "",
                "error": f"Request exception: {exc}",
                "raw": "",
            }

        trace_id = response.headers.get("x-siliconcloud-trace-id", "")
        if response.status_code >= 400:
            return {
                "ok": False,
                "trace_id": trace_id,
                "error": f"SiliconFlow error {response.status_code}",
                "raw": response.text[:4000],
            }

        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            return {
                "ok": False,
                "trace_id": trace_id,
                "error": "No choices returned by provider",
                "raw": json.dumps(body, ensure_ascii=False)[:4000],
            }

        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            content = "\n".join(str(x) for x in content)
        content = str(content or "").strip()

        return {
            "ok": True,
            "trace_id": trace_id,
            "raw": content,
        }

    @staticmethod
    def _build_stage1_prompt(scene: str) -> str:
        return (
            "You are a fire-safety visual extractor. Analyze the image and return STRICT JSON only.\n"
            "Do not give final compliance judgement.\n"
            "JSON schema:\n"
            "{\n"
            '  "scene_observation": "one paragraph visual facts",\n'
            '  "suspected_hazards": ["hazard_1", "hazard_2"],\n'
            '  "keywords": ["keyword1", "keyword2", "keyword3"],\n'
            '  "risk_hint": "safe|warning|danger"\n'
            "}\n"
            f"Scene hint: {scene}."
        )

    @staticmethod
    def _build_stage2_prompt(scene: str, stage1: Dict[str, Any], rules: List[Dict[str, Any]]) -> str:
        rules_text = json.dumps(rules, ensure_ascii=False, indent=2)
        stage1_text = json.dumps(stage1, ensure_ascii=False, indent=2)
        return (
            "You are a fire-safety compliance analyst.\n"
            "Based on STAGE1 observations and RULES, produce final judgement.\n"
            "Only use provided rules as citation basis.\n"
            "If evidence is insufficient, return warning and keep items empty.\n"
            "Return STRICT JSON only, no markdown.\n"
            "JSON schema:\n"
            "{\n"
            '  "overall_risk": "safe|warning|danger",\n'
            '  "summary": "short summary",\n'
            '  "items": [\n'
            "    {\n"
            '      "type": "hazard type",\n'
            '      "risk": "safe|warning|danger",\n'
            '      "desc": "hazard detail",\n'
            '      "suggest": "fix suggestion"\n'
            "    }\n"
            "  ],\n"
            '  "citations": [\n'
            "    {\n"
            '      "article": "clause",\n'
            '      "source": "document name",\n'
            '      "quote": "short supporting quote"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"SCENE: {scene}\n"
            f"STAGE1:\n{stage1_text}\n\n"
            f"RULES:\n{rules_text}\n"
        )

    def _guardrail_no_rules(
        self,
        stage1_result: Dict[str, Any],
        stage1_raw: str,
        retrieval_debug: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "overall_risk": "warning",
            "summary": "No sufficiently relevant regulations were retrieved. Returned conservative result to avoid unsupported inference.",
            "items": [
                {
                    "type": "Insufficient regulatory evidence",
                    "risk": "warning",
                    "desc": "Stage2 compliance inference was skipped because rule retrieval confidence is too low.",
                    "suggest": "Expand the knowledge base or improve scene-specific rule coverage.",
                }
            ],
            "citations": [],
            "stage1_result": stage1_result,
            "raw_output": stage1_raw,
            "raw_output_stage1": stage1_raw,
            "raw_output_stage2": "",
            "_debug": {
                "provider": "knowledge_guardrail",
                "status": "guarded",
                "error": "No relevant rules passed retrieval thresholds",
                "stage1_model": self.vision_model,
                "stage2_model": self.text_model,
                "retrieval": retrieval_debug,
            },
        }

    def _fallback(self, reason: str, stage1_raw: str = "", stage2_raw: str = "", stage1_result: Dict[str, Any] | None = None, rules: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        stage1_result = stage1_result or {}
        rules = rules or []

        fallback_citations: List[Dict[str, str]] = []
        for rule in rules[:3]:
            fallback_citations.append(
                {
                    "article": self._safe_text(rule.get("article"), 80),
                    "source": self._safe_text(rule.get("source"), 120),
                    "quote": self._safe_text(rule.get("text"), 240),
                }
            )

        fallback_summary = "AI analysis is unavailable, returned fallback result."
        if stage1_result.get("scene_observation"):
            fallback_summary = (
                "Stage2 compliance inference timed out. Returned provisional summary from Stage1 observation."
            )

        return {
            "overall_risk": "warning",
            "summary": fallback_summary,
            "items": [
                {
                    "type": "Analysis unavailable",
                    "risk": "warning",
                    "desc": "The AI provider call failed or returned invalid data.",
                    "suggest": "Check API key/model/network and retry.",
                }
            ],
            "citations": fallback_citations,
            "stage1_result": stage1_result,
            "raw_output": stage2_raw or stage1_raw,
            "raw_output_stage1": stage1_raw,
            "raw_output_stage2": stage2_raw,
            "_debug": {
                "provider": "fallback",
                "status": "partial",
                "error": reason,
                "stage1_model": self.vision_model,
                "stage2_model": self.text_model,
                "retrieved_rules": rules,
            },
        }

    def _normalize_final(
        self,
        parsed: Dict[str, Any],
        stage1_result: Dict[str, Any],
        rules: List[Dict[str, Any]],
        retrieval_debug: Dict[str, Any],
        stage1_raw: str,
        stage2_raw: str,
        trace1: str,
        trace2: str,
    ) -> Dict[str, Any]:
        items_in = parsed.get("items")
        normalized_items: List[Dict[str, str]] = []
        if isinstance(items_in, list):
            for item in items_in[:8]:
                if not isinstance(item, dict):
                    continue
                normalized_items.append(
                    {
                        "type": self._safe_text(item.get("type"), 120) or "Unknown hazard",
                        "risk": self._normalize_risk(item.get("risk")),
                        "desc": self._safe_text(item.get("desc"), 1000),
                        "suggest": self._safe_text(item.get("suggest"), 1000),
                    }
                )

        citations_in = parsed.get("citations")
        citations: List[Dict[str, str]] = []
        allowed_pairs = {(str(r.get("article", "")), str(r.get("source", ""))) for r in rules}
        if isinstance(citations_in, list):
            for c in citations_in[:6]:
                if not isinstance(c, dict):
                    continue
                article = self._safe_text(c.get("article"), 80)
                source = self._safe_text(c.get("source"), 120)
                # Anti-hallucination: only keep citations that exist in retrieved rules.
                if (article, source) not in allowed_pairs:
                    continue
                citations.append(
                    {
                        "article": article,
                        "source": source,
                        "quote": self._safe_text(c.get("quote"), 240),
                    }
                )

        # Fallback to retrieved rules if model did not return citations.
        if not citations:
            for rule in rules[:3]:
                citations.append(
                    {
                        "article": self._safe_text(rule.get("article"), 80),
                        "source": self._safe_text(rule.get("source"), 120),
                        "quote": self._safe_text(rule.get("text"), 240),
                    }
                )

        summary = self._safe_text(parsed.get("summary"), 1200)
        if not summary:
            summary = "Model returned no summary."

        return {
            "overall_risk": self._normalize_risk(parsed.get("overall_risk")),
            "summary": summary,
            "items": normalized_items,
            "citations": citations,
            "stage1_result": stage1_result,
            "raw_output": stage2_raw,
            "raw_output_stage1": stage1_raw,
            "raw_output_stage2": stage2_raw,
            "_debug": {
                "provider": "siliconflow",
                "status": "success",
                "stage1_model": self.vision_model,
                "stage2_model": self.text_model,
                "stage1_trace_id": trace1,
                "stage2_trace_id": trace2,
                "retrieved_rules": rules,
                "retrieval": retrieval_debug,
            },
        }

    def analyze_image(self, file_path: str, scene: str = "campus", force_refresh: bool = False) -> Dict[str, Any]:
        image_path = Path(file_path)
        if not image_path.is_absolute():
            image_path = settings.BASE_DIR / image_path
        if not image_path.exists():
            return self._fallback(f"Image not found: {image_path}")

        image_hash = ""
        try:
            image_hash = result_cache_service.compute_image_hash(str(image_path))
        except Exception:
            image_hash = ""

        if image_hash and not force_refresh:
            cached = result_cache_service.get(scene=scene, image_hash=image_hash)
            if cached:
                return self._finalize_with_cache(
                    cached,
                    scene=scene,
                    image_hash=image_hash,
                    cache_hit=True,
                    forced=force_refresh,
                )

        api_key = settings.SILICONFLOW_API_KEY or os.getenv("SILICONFLOW_API_KEY")
        if not api_key:
            return self._fallback("SILICONFLOW_API_KEY is not configured")

        data_url = self._encode_image_to_data_url(str(image_path))

        # Stage 1: visual extraction from image
        stage1_prompt = self._build_stage1_prompt(scene)
        stage1_messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url,
                            "detail": "low",
                        },
                    },
                    {"type": "text", "text": stage1_prompt},
                ],
            }
        ]
        stage1_call = self._chat_completion(
            api_key=api_key,
            model=self.vision_model,
            messages=stage1_messages,
            temperature=0.1,
            max_tokens=500,
        )
        if not stage1_call["ok"]:
            return self._finalize_with_cache(
                self._fallback(stage1_call["error"], stage1_raw=stage1_call.get("raw", "")),
                scene=scene,
                image_hash=image_hash,
                cache_hit=False,
                forced=force_refresh,
            )

        stage1_raw = stage1_call["raw"]
        stage1_parsed = self._extract_json(stage1_raw)
        if stage1_parsed is None:
            return self._finalize_with_cache(
                self._fallback("Stage1 output is not valid JSON", stage1_raw=stage1_raw),
                scene=scene,
                image_hash=image_hash,
                cache_hit=False,
                forced=force_refresh,
            )

        stage1_result = {
            "scene_observation": self._safe_text(stage1_parsed.get("scene_observation"), 1000),
            "suspected_hazards": [self._safe_text(x, 80) for x in (stage1_parsed.get("suspected_hazards") or []) if str(x).strip()][:8],
            "keywords": [self._safe_text(x, 40) for x in (stage1_parsed.get("keywords") or []) if str(x).strip()][:12],
            "risk_hint": self._normalize_risk(stage1_parsed.get("risk_hint")),
        }

        # If Stage1 indicates multiple plugs/devices, inject the safety note into Stage2 prompt.
        stage1_text = " ".join(
            [
                stage1_result.get("scene_observation", ""),
                " ".join(stage1_result.get("suspected_hazards", [])),
                " ".join(stage1_result.get("keywords", [])),
            ]
        ).lower()
        multi_plug_tokens = ["两个插头", "多插头", "多个插头", "插头", "两台设备", "多台设备", "一箱多机"]
        has_multi_plug = any(token in stage1_text for token in multi_plug_tokens) and (
            "两个" in stage1_text or "多" in stage1_text or "两台" in stage1_text or "一箱多机" in stage1_text
        )
        stage1_raw_norm = re.sub(r"\s+", " ", stage1_raw.lower())
        has_two_outlets = (
            bool(re.search(r"\btwo\s+(?:power\s+|electrical\s+)?outlets?\b", stage1_raw_norm))
            or bool(re.search(r"\btwo\s+(?:power\s+|electrical\s+)?outlets?\b", stage1_text))
            or "2 outlets" in stage1_raw_norm
            or "2 outlet" in stage1_raw_norm
            or ("two" in stage1_text and "outlet" in stage1_text)
        )

        # Retrieve rules from knowledge base using stage1 output.
        retrieval_query = " ".join(
            [
                scene,
                stage1_result.get("scene_observation", ""),
                " ".join(stage1_result.get("suspected_hazards", [])),
                " ".join(stage1_result.get("keywords", [])),
            ]
        ).strip()
        retrieval_result = rule_retriever.retrieve_with_debug(
            query=retrieval_query,
            scene=scene,
            top_k=settings.RAG_TOP_K,
            min_score=settings.RAG_MIN_SCORE,
            min_token_hits=settings.RAG_MIN_TOKEN_HITS,
        )
        rules = retrieval_result["rules"]
        retrieval_debug = retrieval_result["debug"]

        # Industrial/construction safety guidance: inject dedicated switch-box rule
        # when visual cues indicate "one box, multiple devices".
        industrial_scenes = {"industrial", "construction", "factory"}
        trigger_text = retrieval_query.lower()
        if scene in industrial_scenes and any(
            token in trigger_text
            for token in ["配电箱", "开关箱", "插头", "一箱多机", "临时用电", "多台设备"]
        ):
            for rule in getattr(rule_retriever, "rules", []):
                if str(rule.get("id", "")) == "IND-POWER-001":
                    if all(str(r.get("id", "")) != "IND-POWER-001" for r in rules):
                        rules = [rule] + list(rules)
                    break

        if has_two_outlets:
            forced_rule = {
                "id": "IND-POWER-001",
                "source": "安全用电管理要点(工业/工地)",
                "article": "临电-01",
                "title": "Dedicated switch box per equipment",
                "scene": ["industrial", "construction", "factory"],
                "hazard_type": "multi_device_one_box",
                "text": "严禁用同一个开关箱直接控制2台及2台以上的用电设备。",
            }
            if all(str(r.get("id", "")) != "IND-POWER-001" for r in rules):
                rules = [forced_rule] + list(rules)
            retrieval_debug = dict(retrieval_debug or {})
            retrieval_debug["force_rule"] = "IND-POWER-001"
            retrieval_debug["force_reason"] = "two_outlets_detected"

        if not rules:
            return self._finalize_with_cache(
                self._guardrail_no_rules(
                    stage1_result=stage1_result,
                    stage1_raw=stage1_raw,
                    retrieval_debug=retrieval_debug,
                ),
                scene=scene,
                image_hash=image_hash,
                cache_hit=False,
                forced=force_refresh,
            )

        # Stage 2: compliance judgement with retrieved rules.
        stage2_prompt = self._build_stage2_prompt(scene, stage1_result, rules)
        if has_multi_plug or has_two_outlets:
            stage2_prompt += (
                "\n\nSAFETY_NOTE: 严禁用同一个开关箱直接控制2台及2台以上的用电设备。"
            )
        stage2_messages = [
            {
                "role": "system",
                "content": "You are a strict fire-safety compliance assistant.",
            },
            {
                "role": "user",
                "content": stage2_prompt,
            },
        ]
        stage2_call = self._chat_completion(
            api_key=api_key,
            model=self.text_model,
            messages=stage2_messages,
            temperature=0.2,
            max_tokens=700,
        )
        if not stage2_call["ok"]:
            return self._finalize_with_cache(
                self._fallback(
                    stage2_call["error"],
                    stage1_raw=stage1_raw,
                    stage2_raw=stage2_call.get("raw", ""),
                    stage1_result=stage1_result,
                    rules=rules,
                ),
                scene=scene,
                image_hash=image_hash,
                cache_hit=False,
                forced=force_refresh,
            )

        stage2_raw = stage2_call["raw"]
        stage2_parsed = self._extract_json(stage2_raw)
        if stage2_parsed is None:
            return self._finalize_with_cache(
                self._fallback(
                    "Stage2 output is not valid JSON",
                    stage1_raw=stage1_raw,
                    stage2_raw=stage2_raw,
                    stage1_result=stage1_result,
                    rules=rules,
                ),
                scene=scene,
                image_hash=image_hash,
                cache_hit=False,
                forced=force_refresh,
            )

        if has_two_outlets:
            items = stage2_parsed.get("items")
            if not isinstance(items, list):
                items = []
            items.append(
                {
                    "type": "用电安全隐患",
                    "risk": "danger",
                    "desc": "检测到配电箱存在两个插头，疑似一箱多机。",
                    "suggest": "严禁用同一个开关箱直接控制2台及2台以上的用电设备。",
                }
            )
            stage2_parsed["items"] = items

        return self._finalize_with_cache(
            self._normalize_final(
                parsed=stage2_parsed,
                stage1_result=stage1_result,
                rules=rules,
                retrieval_debug=retrieval_debug,
                stage1_raw=stage1_raw,
                stage2_raw=stage2_raw,
                trace1=stage1_call.get("trace_id", ""),
                trace2=stage2_call.get("trace_id", ""),
            ),
            scene=scene,
            image_hash=image_hash,
            cache_hit=False,
            forced=force_refresh,
        )


analyzer_service = AnalyzerService()
