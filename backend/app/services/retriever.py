from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import requests

from app.core.config import settings


class RuleRetriever:
    def __init__(self):
        self.rules: List[Dict[str, Any]] = []
        self.meta: Dict[str, Any] = {}
        self._idf: Dict[str, float] = {}
        self._rule_vectors: List[Dict[str, float]] = []
        self._rule_norms: List[float] = []
        self._dense_rule_embeddings: List[List[float]] = []
        self._dense_rule_norms: List[float] = []
        self._dense_index_ready = False
        self._dense_cache_hit = False
        self._last_selection_debug: Dict[str, Any] = {}
        self.base_url = settings.SILICONFLOW_BASE_URL.rstrip("/")
        self.text_model = settings.SILICONFLOW_TEXT_MODEL
        self.embedding_cache_dir = settings.RAG_EMBEDDING_CACHE_DIR
        self.embedding_cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_rules()

    def _load_rules(self) -> None:
        file_path = settings.RULES_FILE
        self.rules = []
        self.meta = {}

        if not file_path.exists():
            self._idf = {}
            self._rule_vectors = []
            self._rule_norms = []
            self._reset_dense_index()
            return

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)

            if isinstance(data, list):
                self.rules = [x for x in data if isinstance(x, dict)]
            elif isinstance(data, dict):
                self.meta = data.get("knowledge_base", {}) if isinstance(data.get("knowledge_base"), dict) else {}
                rules = data.get("rules", [])
                if isinstance(rules, list):
                    self.rules = [x for x in rules if isinstance(x, dict)]
        except Exception:
            self.rules = []
            self.meta = {}

        self._build_vector_index()
        self._reset_dense_index()

    def _reset_dense_index(self) -> None:
        self._dense_rule_embeddings = []
        self._dense_rule_norms = []
        self._dense_index_ready = False
        self._dense_cache_hit = False

    @staticmethod
    def _safe_text(value: Any, max_len: int = 500) -> str:
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

    def _get_api_key(self) -> str:
        return str(settings.SILICONFLOW_API_KEY or os.getenv("SILICONFLOW_API_KEY") or "").strip()

    def _chat_completion(
        self,
        api_key: str,
        messages: List[Dict[str, Any]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 500,
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
                timeout=30,
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

    def _embedding_request(self, api_key: str, inputs: List[str]) -> Dict[str, Any]:
        payload = {
            "model": settings.RAG_EMBEDDING_MODEL,
            "input": inputs,
            "encoding_format": "float",
        }

        try:
            response = requests.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
        except requests.RequestException as exc:
            return {"ok": False, "error": f"request_failed: {exc}", "vectors": []}

        if response.status_code >= 400:
            return {"ok": False, "error": f"provider_http_{response.status_code}", "vectors": []}

        try:
            body = response.json()
        except Exception:
            return {"ok": False, "error": "invalid_json", "vectors": []}

        rows = body.get("data") or []
        if not isinstance(rows, list):
            return {"ok": False, "error": "invalid_data", "vectors": []}

        pairs: List[tuple[int, List[float]]] = []
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            embedding = row.get("embedding")
            if not isinstance(embedding, list):
                continue
            try:
                vec = [float(x) for x in embedding]
            except Exception:
                continue
            pairs.append((int(row.get("index", idx) or idx), vec))

        pairs.sort(key=lambda x: x[0])
        vectors = [vec for _, vec in pairs]
        if len(vectors) != len(inputs):
            return {"ok": False, "error": "embedding_count_mismatch", "vectors": vectors}
        return {"ok": True, "vectors": vectors}

    def _rerank_request(self, api_key: str, query: str, documents: List[str], top_n: int) -> Dict[str, Any]:
        payload = {
            "model": settings.RAG_RERANK_MODEL,
            "query": query,
            "documents": documents,
            "top_n": max(1, min(top_n, len(documents))),
            "return_documents": False,
        }

        try:
            response = requests.post(
                f"{self.base_url}/rerank",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=45,
            )
        except requests.RequestException as exc:
            return {"ok": False, "error": f"request_failed: {exc}", "results": []}

        if response.status_code >= 400:
            return {"ok": False, "error": f"provider_http_{response.status_code}", "results": []}

        try:
            body = response.json()
        except Exception:
            return {"ok": False, "error": "invalid_json", "results": []}

        results = body.get("results") or body.get("data") or []
        if not isinstance(results, list):
            return {"ok": False, "error": "invalid_results", "results": []}
        return {"ok": True, "results": results}

    @staticmethod
    def _dedupe_texts(values: List[str], limit: int | None = None) -> List[str]:
        seen = set()
        items: List[str] = []
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(text)
            if limit and len(items) >= limit:
                break
        return items

    @staticmethod
    def _contains_cjk(text: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", str(text or "")))

    @classmethod
    def _domain_keyword_score(cls, text: str) -> int:
        lowered = str(text or "").lower()
        keywords = [
            "消防",
            "火灾",
            "隐患",
            "整改",
            "疏散",
            "通道",
            "出口",
            "灭火器",
            "消防车通道",
            "电动自行车",
            "充电",
            "配电",
            "电气",
            "巡查",
            "演练",
            "培训",
            "应急预案",
            "fire",
            "hazard",
            "safety",
            "evacuation",
            "extinguisher",
            "e-bike",
            "electrical",
            "inspection",
            "compliance",
        ]
        return sum(1 for token in keywords if token in lowered)

    @classmethod
    def _repair_mojibake(cls, text: str) -> str:
        if not bool(getattr(settings, "RAG_ENABLE_TEXT_REPAIR", True)):
            return str(text or "")

        raw = str(text or "")
        if not raw or not cls._contains_cjk(raw):
            return raw

        try:
            repaired = raw.encode("gbk").decode("utf-8")
        except Exception:
            return raw

        if not repaired or repaired == raw:
            return raw

        raw_score = cls._domain_keyword_score(raw)
        repaired_score = cls._domain_keyword_score(repaired)
        raw_artifacts = raw.count("锛") + raw.count("銆") + raw.count("鈥")
        repaired_artifacts = repaired.count("锛") + repaired.count("銆") + repaired.count("鈥")

        if repaired_score > raw_score:
            return repaired
        if raw_artifacts > repaired_artifacts and repaired_score >= raw_score:
            return repaired
        return raw

    @classmethod
    def _normalize_query_text(cls, text: str) -> str:
        normalized = cls._repair_mojibake(str(text or "").strip())
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"[？?]+$", "", normalized)
        return normalized

    @staticmethod
    def _cjk_ngrams(text: str, min_n: int = 2, max_n: int = 3) -> List[str]:
        grams: List[str] = []
        for block in re.findall(r"[\u4e00-\u9fff]+", text):
            block = block.strip()
            if len(block) < min_n:
                continue
            for n in range(min_n, min(max_n, len(block)) + 1):
                for i in range(0, len(block) - n + 1):
                    grams.append(block[i : i + n])
        return grams

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        text = cls._repair_mojibake(str(text or "")).lower()
        base_tokens = re.findall(r"[a-zA-Z0-9_]{2,}|[\u4e00-\u9fff]{2,}", text)
        grams = cls._cjk_ngrams(text, min_n=2, max_n=3)
        tokens = base_tokens + grams
        return [t for t in tokens if len(t) >= 2]

    @classmethod
    def _expand_query(cls, query: str) -> str:
        text = cls._normalize_query_text(query)
        if not text:
            return text

        expansions: List[str] = []
        lower_text = text.lower()
        canonical_map = [
            (
                ["电动自行车", "电瓶车", "e-bike", "ebike"],
                ["楼道", "公共门厅", "疏散通道", "充电", "停放", "electric bicycle", "stairwell", "corridor", "public lobby"],
            ),
            (
                ["消防车通道", "安全出口", "疏散", "登高操作场地"],
                ["占用", "堵塞", "封闭", "登高操作场地", "fire lane", "evacuation route", "blocked", "rescue access"],
            ),
            (["灭火器", "extinguisher"], ["遮挡", "失效", "压力表", "取用", "blocked", "pressure gauge", "invalid"]),
            (["消火栓", "hydrant"], ["遮挡", "圈占", "取水", "明显标识", "blocked", "occupied"]),
            (["喷淋", "sprinkler"], ["喷头", "遮挡", "损坏", "刷漆", "sprinkler head", "blocked", "painted"]),
            (["报警", "探测器", "detector", "alarm"], ["火灾报警", "故障", "遮挡", "维护", "alarm fault", "maintenance"]),
            (["配电箱", "电气", "电线", "panel", "wiring"], ["过载", "老化", "外露", "临时用电", "overload", "aging wire", "temporary power"]),
            (["插线板", "排插", "大功率", "过载", "超负荷"], ["power strip", "electrical overload", "high-power equipment", "overload"]),
            (["厨房", "排油烟", "kitchen"], ["管道", "清洗", "油垢", "exhaust duct", "grease", "periodic cleaning"]),
            (["应急预案", "演练", "巡查", "培训"], ["消防安全职责", "定期检查", "隐患整改", "emergency plan", "drill", "patrol", "training"]),
            (["整改", "隐患", "未整改", "整改期限"], ["hazard rectification", "corrective action", "deadline"]),
            (["登高", "消防车", "操作场地", "救援场地"], ["rescue access", "operation ground", "fire lane", "blocked"]),
            (["指示标志", "疏散示意图", "出口标志", "疏散标识"], ["evacuation signage", "exit sign", "evacuation map", "wayfinding"]),
            (["配电室", "设备用房", "机房", "控制室"], ["equipment room", "distribution room", "combustible storage", "control room staffing"]),
            (["控制室", "值班", "持证", "双人"], ["control room", "staffing", "duty", "certified operators"]),
            (["动火", "电焊", "气焊", "审批", "监护"], ["hot work", "welding", "approval", "onsite guard"]),
            (["公众聚集场所", "开业", "投入使用", "营业前"], ["public venue", "opening", "fire safety check", "inspection before operation"]),
            (["维护", "保养", "检测", "故障", "报警设备"], ["facility maintenance", "alarm fault", "repair", "detection"]),
            (["易燃易爆", "危险品", "化学品", "液化气", "钢瓶"], ["hazardous goods", "flammable", "explosive", "gas cylinder", "chemical storage"]),
            (["电缆井", "管道井", "竖井"], ["cable shaft", "pipe shaft", "combustibles", "shaft clutter"]),
            (["外窗", "防盗网", "逃生窗"], ["window escape", "anti-theft grill", "rescue obstacle"]),
            (["factory", "industrial", "工地", "施工"], ["临时用电", "开关箱", "电缆拖地", "construction", "switch box", "cable on floor"]),
            (["campus", "school", "学校"], ["校园", "宿舍", "教学楼", "campus", "dormitory"]),
            (["residential", "community", "小区", "住宅"], ["居民区", "高层民用建筑", "residential", "high-rise"]),
            (["office", "办公"], ["办公室", "写字楼", "office building"]),
        ]

        lane_intent_keywords = [
            "fire lane",
            "rescue access",
            "evacuation route",
            "\u6d88\u9632\u8f66\u901a\u9053",
            "\u767b\u9ad8\u64cd\u4f5c\u573a\u5730",
            "\u5b89\u5168\u51fa\u53e3",
            "\u5360\u7528",
            "\u5835\u585e",
            "\u5c01\u95ed",
        ]

        for triggers, related_terms in canonical_map:
            if not any(trigger.lower() in lower_text for trigger in triggers):
                continue
            # Guard against over-triggering "fire lane" expansion for generic "evacuation plan" questions.
            if "fire lane" in [str(x).lower() for x in related_terms]:
                if not any(keyword.lower() in lower_text for keyword in lane_intent_keywords):
                    continue
            expansions.extend(related_terms)

        special_boosts = [
            (
                [
                    "\u767b\u9ad8\u6d88\u9632\u8f66\u64cd\u4f5c\u573a\u5730",
                    "\u6d88\u9632\u8f66\u901a\u9053",
                    "\u6551\u63f4\u573a\u5730",
                    "\u5360\u7528",
                    "\u5835\u585e",
                ],
                ["rescue access", "operation ground", "fire lane", "blocked", "hmbf-22", "firelaw-28"],
            ),
            (
                ["\u5b9a\u671f\u9632\u706b\u68c0\u67e5", "\u5b9a\u671f\u68c0\u67e5", "periodic inspection", "fire inspection"],
                ["periodic inspection requirement", "scheduled fire inspection", "hmbf-35", "firelaw-16"],
            ),
            (
                ["\u5e94\u6025\u9884\u6848", "\u706d\u706b\u548c\u5e94\u6025\u758f\u6563\u9884\u6848", "emergency plan"],
                ["emergency evacuation plan", "fire response plan", "hmbf-43", "firelaw-16"],
            ),
            (
                ["\u6d88\u9632\u6f14\u7ec3", "\u5e94\u6025\u6f14\u7ec3", "evacuation drill", "fire drill"],
                ["regular drill", "hmbf-44", "firelaw-16"],
            ),
        ]
        for trigger_words, boost_terms in special_boosts:
            if any(word.lower() in lower_text for word in trigger_words):
                expansions.extend(boost_terms)

        synonym_map = [
            (["电动车", "电瓶车", "电摩"], ["电动自行车", "停放", "充电"]),
            (["楼道", "楼梯口"], ["疏散走道", "楼梯间", "安全出口", "公共门厅"]),
            (["能放", "可以放", "能不能放"], ["停放", "占用", "堵塞"]),
            (["充电"], ["为电动自行车充电", "疏散走道"]),
            (["灭火器", "fire extinguisher"], ["压力表", "失效", "遮挡", "取用"]),
            (["消火栓", "hydrant"], ["遮挡", "圈占", "取水", "明显标识"]),
            (["防火门", "fire door"], ["常闭", "闭门器", "顺序器", "门扇"]),
            (["消防通道", "车道", "fire lane", "fire access"], ["消防车通道", "登高操作场地", "占用", "堵塞"]),
            (["喷淋", "sprinkler"], ["喷头", "挡住", "损坏", "覆盖"]),
            (["报警器", "探测器", "alarm", "detector"], ["火灾报警", "探测器", "遮挡", "故障"]),
            (["outlet", "outlets", "socket", "sockets", "power outlet"], ["插座", "电源插座", "墙面插座"]),
            (["two outlets", "two sockets", "two plugs", "dual outlet", "double outlet"], ["两个插座", "两个插头", "双插"]),
            (["plug", "plugs"], ["插头", "多插头"]),
            (["power strip", "extension cord", "extension cable"], ["插线板", "排插", "接线板", "延长线"]),
            (
                ["electrical panel", "distribution box", "switch box", "panel box", "panelboard"],
                ["配电箱", "开关箱", "电箱"],
            ),
            (["breaker", "circuit breaker"], ["断路器", "空气开关"]),
            (["wiring", "wire", "cable"], ["电线", "线路", "线缆"]),
            (["exposed wiring", "exposed wire", "exposed cable"], ["线路裸露", "电线外露", "线缆外露"]),
            (["overload", "overloaded"], ["过载", "超负荷"]),
            (["open panel", "panel open", "door open"], ["配电箱敞开", "箱门未关闭"]),
            (["temporary power", "temporary wiring"], ["临时用电", "临时线路"]),
            (["cable on floor", "wires on floor", "cord on floor"], ["电缆拖地", "线路拖地"]),
            (["construction site", "jobsite"], ["工地", "施工现场"]),
            (["factory", "industrial"], ["工厂", "工业"]),
            (["campus", "school"], ["校园", "学校"]),
            (["residential", "community", "apartment"], ["居民区", "小区", "住宅"]),
            (["office"], ["办公区", "办公楼"]),
        ]

        for triggers, related_terms in synonym_map:
            if any(trigger.lower() in lower_text for trigger in triggers):
                expansions.extend(related_terms)

        if not expansions:
            return text

        merged = " ".join([text] + expansions)
        return merged.strip()

    @classmethod
    def _rule_to_text(cls, rule: Dict[str, Any]) -> str:
        text_parts = [
            str(rule.get("id", "")),
            str(rule.get("source", "")),
            str(rule.get("article", "")),
            str(rule.get("title", "")),
            str(rule.get("text", "")),
            str(rule.get("hazard_type", "")),
            " ".join(rule.get("tags", []) if isinstance(rule.get("tags"), list) else []),
            " ".join(rule.get("scene", []) if isinstance(rule.get("scene"), list) else []),
        ]
        normalized_parts = [cls._repair_mojibake(part) for part in text_parts]
        return " ".join(normalized_parts).strip()

    @staticmethod
    def _tfidf_vector(tokens: List[str], idf: Dict[str, float]) -> Dict[str, float]:
        if not tokens:
            return {}

        counts = Counter(tokens)
        total = float(sum(counts.values()) or 1.0)
        vec: Dict[str, float] = {}
        for tok, cnt in counts.items():
            tf = cnt / total
            vec[tok] = tf * idf.get(tok, 0.0)
        return vec

    @staticmethod
    def _norm(vec: Dict[str, float]) -> float:
        return math.sqrt(sum(v * v for v in vec.values()))

    @staticmethod
    def _dense_norm(vec: List[float]) -> float:
        return math.sqrt(sum(v * v for v in vec))

    @staticmethod
    def _cosine(vec_a: Dict[str, float], norm_a: float, vec_b: Dict[str, float], norm_b: float) -> float:
        if norm_a <= 0 or norm_b <= 0:
            return 0.0

        if len(vec_a) > len(vec_b):
            vec_a, vec_b = vec_b, vec_a
            norm_a, norm_b = norm_b, norm_a

        dot = 0.0
        for tok, wa in vec_a.items():
            wb = vec_b.get(tok)
            if wb is not None:
                dot += wa * wb

        return float(dot / (norm_a * norm_b)) if dot > 0 else 0.0

    @staticmethod
    def _dense_cosine(vec_a: List[float], norm_a: float, vec_b: List[float], norm_b: float) -> float:
        if norm_a <= 0 or norm_b <= 0:
            return 0.0
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = 0.0
        for idx, value in enumerate(vec_a):
            dot += value * vec_b[idx]
        return float(dot / (norm_a * norm_b))

    @staticmethod
    def _normalize_dense_score(raw_score: float) -> float:
        return max(0.0, min(1.0, (float(raw_score) + 1.0) / 2.0))

    @staticmethod
    def _normalize_rerank_score(raw_score: float) -> float:
        return max(0.0, min(1.0, float(raw_score)))

    @staticmethod
    def _normalize_rerank_scores(scores: Dict[int, float]) -> Dict[int, float]:
        if not scores:
            return {}
        values = list(scores.values())
        low = min(values)
        high = max(values)
        if high - low > 1e-9:
            return {idx: (value - low) / (high - low) for idx, value in scores.items()}

        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        total = max(len(ordered) - 1, 1)
        return {idx: 1.0 - (rank / total) for rank, (idx, _) in enumerate(ordered)}

    def _build_vector_index(self) -> None:
        self._idf = {}
        self._rule_vectors = []
        self._rule_norms = []
        if not self.rules:
            return

        doc_tokens: List[List[str]] = []
        df: Counter[str] = Counter()
        for rule in self.rules:
            tokens = self._tokenize(self._rule_to_text(rule))
            doc_tokens.append(tokens)
            for tok in set(tokens):
                df[tok] += 1

        n_docs = len(doc_tokens)
        self._idf = {tok: math.log((1.0 + n_docs) / (1.0 + doc_freq)) + 1.0 for tok, doc_freq in df.items()}

        for tokens in doc_tokens:
            vec = self._tfidf_vector(tokens, self._idf)
            self._rule_vectors.append(vec)
            self._rule_norms.append(self._norm(vec))

    def _dense_cache_signature(self) -> str:
        hasher = hashlib.sha256()
        hasher.update(str(settings.RAG_EMBEDDING_MODEL).encode("utf-8"))
        hasher.update(str(self.meta.get("version", "")).encode("utf-8"))
        for rule in self.rules:
            hasher.update(str(rule.get("id", "")).encode("utf-8"))
            hasher.update(self._rule_to_text(rule).encode("utf-8", errors="ignore"))
        return hasher.hexdigest()[:24]

    def _dense_cache_file(self) -> Path:
        safe_model = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(settings.RAG_EMBEDDING_MODEL))
        return self.embedding_cache_dir / f"{safe_model}_{self._dense_cache_signature()}.json"

    def _load_dense_embeddings_from_cache(self) -> bool:
        cache_file = self._dense_cache_file()
        if not cache_file.exists():
            return False

        try:
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            return False

        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(self.rules):
            return False

        vectors: List[List[float]] = []
        norms: List[float] = []
        for row in embeddings:
            if not isinstance(row, list):
                return False
            try:
                vec = [float(x) for x in row]
            except Exception:
                return False
            vectors.append(vec)
            norms.append(self._dense_norm(vec))

        self._dense_rule_embeddings = vectors
        self._dense_rule_norms = norms
        self._dense_index_ready = True
        self._dense_cache_hit = True
        return True

    def _save_dense_embeddings_to_cache(self) -> None:
        if not self._dense_rule_embeddings:
            return

        payload = {
            "model": settings.RAG_EMBEDDING_MODEL,
            "knowledge_base_version": self.meta.get("version", ""),
            "rule_count": len(self.rules),
            "embeddings": self._dense_rule_embeddings,
        }
        cache_file = self._dense_cache_file()
        temp_file = cache_file.with_suffix(".tmp")
        try:
            temp_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temp_file.replace(cache_file)
        except Exception:
            try:
                temp_file.unlink(missing_ok=True)
            except Exception:
                pass

    def _ensure_dense_index(self, api_key: str) -> bool:
        if not settings.RAG_ENABLE_DENSE_RETRIEVAL or not api_key or not self.rules:
            return False
        if self._dense_index_ready and len(self._dense_rule_embeddings) == len(self.rules):
            return True
        if self._load_dense_embeddings_from_cache():
            return True

        rule_texts = [self._rule_to_text(rule) for rule in self.rules]
        batch_size = max(int(settings.RAG_EMBEDDING_BATCH_SIZE), 1)
        vectors: List[List[float]] = []
        for index in range(0, len(rule_texts), batch_size):
            batch = rule_texts[index : index + batch_size]
            result = self._embedding_request(api_key, batch)
            if not result.get("ok"):
                self._reset_dense_index()
                return False
            vectors.extend(result.get("vectors", []))

        if len(vectors) != len(self.rules):
            self._reset_dense_index()
            return False

        self._dense_rule_embeddings = vectors
        self._dense_rule_norms = [self._dense_norm(vec) for vec in vectors]
        self._dense_index_ready = True
        self._dense_cache_hit = False
        self._save_dense_embeddings_to_cache()
        return True

    def _compute_dense_scores(self, api_key: str, query_text: str) -> Dict[str, float]:
        if not self._ensure_dense_index(api_key):
            return {}

        result = self._embedding_request(api_key, [query_text])
        if not result.get("ok"):
            return {}

        vectors = result.get("vectors", [])
        if not vectors:
            return {}
        query_vec = vectors[0]
        query_norm = self._dense_norm(query_vec)

        scores: Dict[str, float] = {}
        for idx, rule in enumerate(self.rules):
            if idx >= len(self._dense_rule_embeddings):
                break
            rule_vec = self._dense_rule_embeddings[idx]
            rule_norm = self._dense_rule_norms[idx] if idx < len(self._dense_rule_norms) else 0.0
            scores[str(rule.get("id", ""))] = self._dense_cosine(query_vec, query_norm, rule_vec, rule_norm)
        return scores

    @staticmethod
    def _normalize_lexical_score(raw_score: float) -> float:
        return max(0.0, min(1.0, raw_score / 8.0))

    def _score_rule(
        self,
        rule_idx: int,
        rule: Dict[str, Any],
        query_tokens: List[str],
        query_vec: Dict[str, float],
        query_norm: float,
        scene: str,
    ) -> Dict[str, Any]:
        haystack = self._rule_to_text(rule).lower()
        matched_tokens: List[str] = []
        for token in set(query_tokens):
            if token in haystack:
                matched_tokens.append(token)

        token_hits = len(matched_tokens)
        overlap_ratio = token_hits / max(len(set(query_tokens)), 1)
        scene_list = rule.get("scene", [])
        scene_match = bool(isinstance(scene_list, list) and scene in scene_list)

        lexical_score = token_hits * 1.0 + overlap_ratio * 2.0 + (1.2 if scene_match else 0.0)
        lexical_norm = self._normalize_lexical_score(lexical_score)

        rule_vec = self._rule_vectors[rule_idx] if rule_idx < len(self._rule_vectors) else {}
        rule_norm = self._rule_norms[rule_idx] if rule_idx < len(self._rule_norms) else 0.0
        vector_score = self._cosine(query_vec, query_norm, rule_vec, rule_norm)

        mode = str(settings.RAG_RETRIEVAL_MODE or "hybrid").strip().lower()
        vector_weight = float(settings.RAG_VECTOR_WEIGHT)
        lexical_weight = float(settings.RAG_LEXICAL_WEIGHT)
        total_weight = max(vector_weight + lexical_weight, 1e-6)
        vector_weight = vector_weight / total_weight
        lexical_weight = lexical_weight / total_weight
        scene_bonus = float(settings.RAG_SCENE_BONUS) if scene_match else 0.0

        if mode == "keyword":
            final_score = lexical_norm + scene_bonus
        elif mode == "vector":
            final_score = vector_score + scene_bonus
        else:
            final_score = lexical_weight * lexical_norm + vector_weight * vector_score + scene_bonus

        return {
            "lexical_score": lexical_score,
            "lexical_norm": lexical_norm,
            "vector_score": vector_score,
            "final_score": round(float(final_score), 6),
            "token_hits": token_hits,
            "matched_tokens": matched_tokens,
            "scene_match": scene_match,
        }

    def _split_sub_questions_heuristic(self, query: str) -> List[str]:
        text = self._normalize_query_text(query)
        if not text:
            return []

        parts = re.split(r"[；;。！？!?]\s*|(?:并且|以及|同时|另外|还有|或者|还是|并且想知道|同时想知道)", text)
        if len(parts) <= 1 and "分别" in text:
            pair_parts = re.split(r"和|与|及", text)
            if len(pair_parts) >= 2:
                prefix = "分别违反什么规定"
                rebuilt: List[str] = []
                for item in pair_parts[: max(int(settings.RAG_SUBQUERY_MAX), 1)]:
                    cleaned = self._normalize_query_text(item.replace("分别", "").replace("违反什么规定", ""))
                    if cleaned:
                        rebuilt.append(f"{cleaned} {prefix}".strip())
                parts = rebuilt or parts
        parts = self._dedupe_texts(parts, limit=max(int(settings.RAG_SUBQUERY_MAX), 1))
        if len(parts) <= 1:
            return []
        return [item for item in parts if len(item) >= 4]

    def _rewrite_query_heuristic(self, query: str, scene: str) -> Dict[str, Any]:
        raw = self._normalize_query_text(query)
        if not raw:
            return {"rewrite": "", "multi_queries": [], "sub_questions": []}

        rewrite = raw
        fillers = [
            "帮我看看",
            "帮我判断",
            "想问一下",
            "请问",
            "我想知道",
            "麻烦问下",
            "能不能",
            "是否可以",
            "合不合法",
            "算不算违规",
        ]
        for filler in fillers:
            rewrite = rewrite.replace(filler, "")
        rewrite = self._normalize_query_text(rewrite)

        legal_terms: List[str] = []
        if any(word in raw for word in ["法规", "法条", "条款", "规范", "依据", "合法吗", "违规", "处罚"]):
            legal_terms.extend(["消防法", "规定", "条款", "要求"])
        if any(word in raw for word in ["整改", "怎么做", "处理", "改进"]):
            legal_terms.extend(["整改", "措施", "要求"])
        if scene:
            legal_terms.append(scene)

        expanded_rewrite = self._dedupe_texts([rewrite, f"{rewrite} {' '.join(legal_terms)}".strip()], limit=1)[0]
        multi_queries: List[str] = [raw]
        expanded = self._expand_query(expanded_rewrite)
        if expanded and expanded != expanded_rewrite:
            multi_queries.append(expanded)

        intent_templates = [
            ("电动自行车" if any(k in raw for k in ["电动车", "电瓶车", "电动自行车"]) else ""),
            ("疏散通道 安全出口 消防车通道" if any(k in raw for k in ["楼道", "走道", "通道", "出口", "车道"]) else ""),
            ("防火门 常闭 闭门器" if "防火门" in raw else ""),
            ("灭火器 消火栓 喷淋 探测器 完好 有效 遮挡" if any(k in raw for k in ["灭火器", "消火栓", "喷淋", "报警", "探测器"]) else ""),
        ]
        for template in intent_templates:
            if template:
                multi_queries.append(f"{expanded_rewrite} {template}".strip())

        if any(word in raw for word in ["处罚", "罚款", "责任"]):
            multi_queries.append(f"{expanded_rewrite} 处罚 罚款 责任".strip())
        if any(word in raw for word in ["依据", "条款", "法规", "规范"]):
            multi_queries.append(f"{expanded_rewrite} 法规依据 条款 规范".strip())

        sub_questions = self._split_sub_questions_heuristic(raw)
        return {
            "rewrite": expanded_rewrite,
            "multi_queries": self._dedupe_texts(multi_queries, limit=max(int(settings.RAG_MULTI_QUERY_MAX), 1)),
            "sub_questions": sub_questions,
        }

    def _rewrite_query_llm(self, query: str, scene: str) -> Dict[str, Any] | None:
        api_key = self._get_api_key()
        if not api_key or not settings.RAG_QUERY_REWRITE_USE_LLM:
            return None

        messages = [
            {
                "role": "system",
                "content": (
                    "你是消防法规检索查询改写器。"
                    "只输出 JSON，不要 markdown。"
                    "保留用户原始语义，不要臆造法规条款。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "把用户问题改写为更适合消防法规检索的查询。"
                    "返回 JSON: "
                    "{\"rewrite\":\"...\",\"multi_queries\":[\"...\"],\"sub_questions\":[\"...\"]}\n\n"
                    f"SCENE: {scene}\n"
                    f"QUESTION: {query}"
                ),
            },
        ]
        result = self._chat_completion(api_key, messages, temperature=0.1, max_tokens=260)
        if not result.get("ok"):
            return None

        parsed = self._extract_json(str(result.get("raw", "")))
        if not isinstance(parsed, dict):
            return None

        rewrite = self._safe_text(parsed.get("rewrite"), 500)
        multi_queries = [self._safe_text(item, 300) for item in (parsed.get("multi_queries") or [])]
        sub_questions = [self._safe_text(item, 300) for item in (parsed.get("sub_questions") or [])]

        return {
            "rewrite": rewrite,
            "multi_queries": self._dedupe_texts(multi_queries, limit=max(int(settings.RAG_MULTI_QUERY_MAX), 1)),
            "sub_questions": self._dedupe_texts(sub_questions, limit=max(int(settings.RAG_SUBQUERY_MAX), 1)),
        }

    def _prepare_queries(self, query: str, scene: str) -> Dict[str, Any]:
        original = self._normalize_query_text(query)
        heuristic = self._rewrite_query_heuristic(original, scene)
        llm_bundle = self._rewrite_query_llm(original, scene) if settings.RAG_ENABLE_QUERY_REWRITE else None

        rewrite = self._safe_text((llm_bundle or {}).get("rewrite"), 500) or heuristic.get("rewrite") or original
        multi_queries = self._dedupe_texts(
            [rewrite] + list((llm_bundle or {}).get("multi_queries") or []) + list(heuristic.get("multi_queries") or []),
            limit=max(int(settings.RAG_MULTI_QUERY_MAX), 1),
        )
        sub_questions = self._dedupe_texts(
            list((llm_bundle or {}).get("sub_questions") or []) + list(heuristic.get("sub_questions") or []),
            limit=max(int(settings.RAG_SUBQUERY_MAX), 1),
        )

        evidence_tree_enabled = bool(settings.RAG_ENABLE_EVIDENCE_TREE_SEARCH)
        normalized_scene = self._normalize_query_text(scene)
        scene_key = normalized_scene.lower()
        scene_is_specific = bool(normalized_scene) and scene_key not in {"unknown", "default", "general", "all"}
        hazard_hints = sorted(self._infer_hazard_hints(f"{original} {rewrite}"))

        hazard_branch_queries: List[Dict[str, str]] = []
        hazard_templates: Dict[str, str] = {
            "e_bike_charging_in_public_area": "e-bike charging and parking fire safety requirements",
            "evacuation_or_lane_blocked": "fire lane and evacuation path obstruction requirements",
            "fire_lane_parking": "fire lane obstruction requirements",
            "extinguisher_blocked": "fire extinguisher accessibility requirements",
            "hydrant_blocked": "hydrant accessibility and operation requirements",
            "sprinkler_blocked": "sprinkler head obstruction and spacing requirements",
            "alarm_detector_shielded": "alarm detector coverage and shielding requirements",
            "alarm_device_fault": "fire alarm maintenance and fault handling requirements",
            "electrical_overload": "electrical overload and temporary wiring requirements",
            "aging_wire": "aging wiring inspection and replacement requirements",
            "kitchen_exhaust": "kitchen exhaust duct and grease cleaning requirements",
            "gas_cylinder_indoor": "gas cylinder indoor storage requirements",
            "hazardous_goods_storage": "hazardous goods storage and separation requirements",
            "shaft_clutter": "shaft and pipe well combustible storage prohibition requirements",
            "window_escape_obstacle": "escape window and opening clearance requirements",
            "equipment_room_storage": "equipment room combustible storage prohibition requirements",
            "control_room_staffing": "fire control room staffing and duty requirements",
            "daily_patrol_missing": "daily patrol checklist requirements",
            "periodic_inspection_missing": "periodic fire inspection requirements",
            "hazard_rectification_delay": "hazard rectification timeline requirements",
            "training_missing": "fire training and awareness requirements",
            "evacuation_map_missing": "evacuation signage and map posting requirements",
            "signage_blocked": "safety signage visibility requirements",
            "emergency_plan_missing": "emergency response plan requirements",
            "drill_missing": "fire drill frequency requirements",
            "hot_work_without_approval": "hot work approval and isolation requirements",
            "public_venue_opening_check": "opening and operation fire safety check requirements",
            "facility_maintenance_missing": "facility maintenance and testing requirements",
        }
        hazard_branch_max = max(int(settings.RAG_EVIDENCE_TREE_HAZARD_BRANCH_MAX), 0) if evidence_tree_enabled else 0
        for hazard in hazard_hints[:hazard_branch_max]:
            template = hazard_templates.get(hazard) or hazard.replace("_", " ")
            text = f"{template} in {normalized_scene} scene" if scene_is_specific else template
            hazard_branch_queries.append({"hazard_type": hazard, "text": self._normalize_query_text(text)})

        retrieval_queries: List[Dict[str, Any]] = [
            {"kind": "original", "text": original, "path": "root", "depth": 0, "branch": "root"}
        ]
        if rewrite and rewrite.lower() != original.lower():
            retrieval_queries.append(
                {"kind": "rewrite", "text": rewrite, "path": "root/rewrite", "depth": 1, "branch": "rewrite"}
            )
        if evidence_tree_enabled and scene_is_specific:
            scene_query = self._normalize_query_text(f"fire safety requirements in {normalized_scene} scene")
            retrieval_queries.append(
                {"kind": "scene_query", "text": scene_query, "path": "root/scene", "depth": 1, "branch": "scene"}
            )
        for idx, item in enumerate(multi_queries):
            retrieval_queries.append(
                {"kind": "multi_query", "text": item, "path": f"root/multi/{idx + 1}", "depth": 2, "branch": "multi"}
            )
        for idx, item in enumerate(sub_questions):
            retrieval_queries.append(
                {
                    "kind": "sub_question",
                    "text": item,
                    "path": f"root/sub/{idx + 1}",
                    "depth": 2,
                    "branch": "sub_question",
                }
            )
        for node in hazard_branch_queries:
            hazard_type = str(node.get("hazard_type", "")).strip() or "generic"
            retrieval_queries.append(
                {
                    "kind": "hazard_branch",
                    "text": self._normalize_query_text(node.get("text", "")),
                    "path": f"root/hazard/{hazard_type}",
                    "depth": 2,
                    "branch": "hazard",
                    "hazard_type": hazard_type,
                }
            )

        cleaned_queries: List[Dict[str, Any]] = []
        seen = set()
        for item in retrieval_queries:
            text_value = self._normalize_query_text(item.get("text", ""))
            if not text_value:
                continue
            key = f"{str(item.get('path', '')).lower()}::{text_value.lower()}"
            if key in seen:
                continue
            seen.add(key)
            cleaned_queries.append(
                {
                    "kind": item.get("kind", "original"),
                    "text": text_value,
                    "path": item.get("path", "root"),
                    "depth": int(item.get("depth", 0) or 0),
                    "branch": item.get("branch", "root"),
                    "hazard_type": item.get("hazard_type", ""),
                }
            )

        return {
            "original_query": original,
            "rewrite": rewrite,
            "multi_queries": multi_queries,
            "sub_questions": sub_questions,
            "retrieval_queries": cleaned_queries,
            "strategy": "llm_plus_heuristic" if llm_bundle else "heuristic",
            "query_tree": {
                "enabled": evidence_tree_enabled,
                "scene": normalized_scene if scene_is_specific else "",
                "hazard_hints": hazard_hints,
                "hazard_branch_count": len(hazard_branch_queries),
                "total_nodes": len(cleaned_queries),
            },
        }

    def _apply_dynamic_query_budget(self, prepared: Dict[str, Any]) -> Dict[str, Any]:
        queries = list(prepared.get("retrieval_queries", []))
        if not queries:
            return {"queries": [], "debug": {"enabled": False, "budget_level": "none", "total_queries": 0, "active_queries": 0}}

        if not bool(settings.RAG_ENABLE_DYNAMIC_QUERY_BUDGET):
            return {
                "queries": queries,
                "debug": {
                    "enabled": False,
                    "budget_level": "disabled",
                    "total_queries": len(queries),
                    "active_queries": len(queries),
                },
            }

        original_query = str(prepared.get("original_query", ""))
        token_count = len(self._tokenize(original_query))
        sub_question_count = len(prepared.get("sub_questions", []))
        multi_query_count = len(prepared.get("multi_queries", []))
        query_tree = prepared.get("query_tree", {})
        if not isinstance(query_tree, dict):
            query_tree = {}
        hazard_hints = query_tree.get("hazard_hints", [])
        hazard_count = len(hazard_hints) if isinstance(hazard_hints, list) else 0
        scene_text = str(query_tree.get("scene", "") or "").strip().lower()
        industrial_indicator = 1 if (
            scene_text in {"industrial", "industry", "factory", "warehouse", "plant", "workshop", "industrial_park"}
            or any(marker in scene_text for marker in ["industrial", "factory", "warehouse", "plant", "workshop", "工厂", "工业", "厂房", "车间", "仓库"])
        ) else 0
        conflict_count = max(0, sub_question_count + multi_query_count - 1)

        simple_th = int(settings.RAG_QUERY_BUDGET_TOKEN_THRESHOLD_SIMPLE)
        medium_th = int(settings.RAG_QUERY_BUDGET_TOKEN_THRESHOLD_MEDIUM)

        if bool(settings.RAG_QUERY_BUDGET_USE_SIGMOID):
            raw_complexity = (
                float(settings.RAG_QUERY_BUDGET_LAMBDA_LENGTH) * token_count
                + float(settings.RAG_QUERY_BUDGET_LAMBDA_HAZARD) * hazard_count
                + float(settings.RAG_QUERY_BUDGET_LAMBDA_INDUSTRIAL) * industrial_indicator
                + float(settings.RAG_QUERY_BUDGET_LAMBDA_CONFLICT) * conflict_count
            )
            centered_complexity = raw_complexity - float(settings.RAG_QUERY_BUDGET_SIGMOID_CENTER)
            eta = float(settings.RAG_QUERY_BUDGET_SIGMOID_ETA)
            try:
                budget_ratio = 1.0 / (1.0 + math.exp(-eta * centered_complexity))
            except OverflowError:
                budget_ratio = 0.0 if centered_complexity < 0 else 1.0

            min_budget = max(int(settings.RAG_QUERY_BUDGET_SIMPLE), 1)
            medium_budget = max(int(settings.RAG_QUERY_BUDGET_MEDIUM), min_budget)
            max_budget = max(int(settings.RAG_QUERY_BUDGET_HARD), medium_budget)
            budget = int(round(min_budget + (max_budget - min_budget) * budget_ratio))
            budget = max(min_budget, min(max_budget, budget))
            if budget <= min_budget:
                level = "simple"
            elif budget <= medium_budget:
                level = "medium"
            else:
                level = "hard"
            budget_mode = "sigmoid"
        else:
            if token_count <= simple_th and sub_question_count == 0 and multi_query_count <= 2:
                level = "simple"
                budget = max(int(settings.RAG_QUERY_BUDGET_SIMPLE), 1)
            elif token_count <= medium_th and sub_question_count <= 1:
                level = "medium"
                budget = max(int(settings.RAG_QUERY_BUDGET_MEDIUM), 2)
            else:
                level = "hard"
                budget = max(int(settings.RAG_QUERY_BUDGET_HARD), 3)
            raw_complexity = float(token_count + sub_question_count + multi_query_count)
            budget_ratio = 0.0
            budget_mode = "bucket"

        selected: List[Dict[str, str]] = []
        selected_keys = set()
        for kind in ["original", "rewrite", "scene_query", "hazard_branch", "multi_query", "sub_question"]:
            for item in queries:
                if item.get("kind") != kind:
                    continue
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                key = f"{kind}:{text.lower()}"
                if key in selected_keys:
                    continue
                selected.append(item)
                selected_keys.add(key)
                if len(selected) >= budget:
                    break
            if len(selected) >= budget:
                break

        if not selected:
            selected = queries[:budget]

        return {
            "queries": selected,
            "debug": {
                "enabled": True,
                "budget_mode": budget_mode,
                "budget_level": level,
                "budget": budget,
                "token_count": token_count,
                "hazard_count": hazard_count,
                "industrial_indicator": industrial_indicator,
                "conflict_count": conflict_count,
                "complexity": round(raw_complexity, 4),
                "sigmoid_ratio": round(budget_ratio, 4),
                "sub_question_count": sub_question_count,
                "multi_query_count": multi_query_count,
                "total_queries": len(queries),
                "active_queries": len(selected),
                "active_kinds": [str(item.get("kind", "")) for item in selected],
            },
        }

    @staticmethod
    def _infer_hazard_hints(query_text: str) -> set[str]:
        text = str(query_text or "").lower()
        hints: set[str] = set()

        mapping: List[tuple[List[str], List[str]]] = [
            (["电动自行车", "电瓶车", "e-bike", "楼道充电", "stairwell"], ["e_bike_charging_in_public_area", "e_bike_penalty"]),
            (["消防车通道", "登高", "rescue access", "fire lane"], ["fire_lane_parking", "evacuation_or_lane_blocked"]),
            (["灭火器", "extinguisher"], ["extinguisher_blocked"]),
            (["消火栓", "hydrant"], ["hydrant_blocked"]),
            (["喷淋", "sprinkler"], ["sprinkler_blocked"]),
            (["报警", "探测器", "detector", "alarm"], ["alarm_detector_shielded", "alarm_device_fault", "facility_maintenance_missing"]),
            (["插线板", "过载", "电线", "配电箱", "wiring", "overload"], ["electrical_overload", "aging_wire"]),
            (["厨房", "排油烟", "kitchen"], ["kitchen_exhaust"]),
            (["液化气", "钢瓶", "gas cylinder"], ["gas_cylinder_indoor", "hazardous_goods_storage"]),
            (["危险品", "易燃易爆", "化学品", "hazardous"], ["hazardous_goods_storage"]),
            (["电缆井", "管道井", "shaft"], ["shaft_clutter"]),
            (["外窗", "防盗网", "window"], ["window_escape_obstacle"]),
            (["设备用房", "配电室", "equipment room"], ["equipment_room_storage"]),
            (["控制室", "值班", "staffing"], ["control_room_staffing"]),
            (["巡查", "daily patrol"], ["daily_patrol_missing"]),
            (["定期检查", "防火检查", "periodic inspection"], ["periodic_inspection_missing"]),
            (["整改", "未整改", "rectification"], ["hazard_rectification_delay"]),
            (["培训", "training"], ["training_missing"]),
            (["疏散示意图", "出口标志", "evacuation map", "signage"], ["evacuation_map_missing", "signage_blocked"]),
            (["应急预案", "emergency plan"], ["emergency_plan_missing"]),
            (["演练", "drill"], ["drill_missing"]),
            (["动火", "电焊", "welding", "hot work"], ["hot_work_without_approval"]),
            (["公众聚集场所", "开业", "opening check"], ["public_venue_opening_check"]),
            (["维护", "保养", "检测", "maintenance"], ["facility_maintenance_missing"]),
        ]

        for keywords, hazard_types in mapping:
            if any(keyword.lower() in text for keyword in keywords):
                hints.update(hazard_types)
        return hints

    @staticmethod
    def _hazard_hint_bonus(rule: Dict[str, Any], hazard_hints: set[str]) -> float:
        if not hazard_hints or not bool(settings.RAG_ENABLE_HAZARD_HINT_ROUTING):
            return 0.0
        hazard_type = str(rule.get("hazard_type", "")).strip()
        if not hazard_type:
            return 0.0
        if hazard_type in hazard_hints:
            return float(settings.RAG_HAZARD_HINT_BONUS)
        return 0.0

    def _blend_retrieval_score(self, sparse_score: float, dense_score_norm: float) -> float:
        weight = max(0.0, min(float(settings.RAG_DENSE_WEIGHT), 0.95))
        if dense_score_norm <= 0:
            return float(sparse_score)
        return (1.0 - weight) * float(sparse_score) + weight * float(dense_score_norm)

    def _apply_rerank(self, api_key: str, query_text: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not settings.RAG_ENABLE_RERANK or not api_key or not candidates:
            return {"applied": False, "error": "disabled_or_missing_api_key"}

        top_n = max(1, min(int(settings.RAG_RERANK_TOP_N), len(candidates)))
        pool = [dict(item) for item in candidates[:top_n]]
        documents = [self._rule_to_text(item) for item in pool]
        result = self._rerank_request(api_key, query_text, documents, top_n=top_n)
        if not result.get("ok"):
            return {"applied": False, "error": result.get("error", "rerank_failed")}

        rerank_scores: Dict[int, float] = {}
        for row in result.get("results", []):
            if not isinstance(row, dict):
                continue
            index = row.get("index")
            if index is None:
                continue
            try:
                rerank_scores[int(index)] = float(row.get("relevance_score", 0.0))
            except Exception:
                continue

        rerank_norms = self._normalize_rerank_scores(rerank_scores)
        weight = max(0.0, min(float(settings.RAG_RERANK_WEIGHT), 0.98))
        updated: List[Dict[str, Any]] = []
        for idx, item in enumerate(pool):
            candidate = dict(item)
            rerank_raw = rerank_scores.get(idx, 0.0)
            rerank_norm = rerank_norms.get(idx, 0.0)
            candidate["rerank_score"] = round(rerank_raw, 4)
            candidate["rerank_score_norm"] = round(rerank_norm, 4)
            candidate["score_pre_rerank"] = round(float(candidate.get("score", 0.0)), 4)
            if rerank_norm > 0:
                candidate["score"] = round(
                    (1.0 - weight) * float(candidate.get("score", 0.0)) + weight * rerank_norm,
                    4,
                )
            updated.append(candidate)

        updated.extend([dict(item) for item in candidates[top_n:]])
        updated.sort(
            key=lambda x: (
                float(x.get("score", 0.0)),
                int(x.get("matched_query_count", 0)),
                float(x.get("rerank_score", 0.0)),
                float(x.get("dense_score_raw", 0.0)),
                float(x.get("vector_score", 0.0)),
                float(x.get("lexical_score", 0.0)),
            ),
            reverse=True,
        )
        return {
            "applied": True,
            "error": "",
            "rerank_top_n": top_n,
            "results": updated,
        }

    @staticmethod
    def _jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
        if not tokens_a or not tokens_b:
            return 0.0
        union = tokens_a | tokens_b
        if not union:
            return 0.0
        return len(tokens_a & tokens_b) / len(union)

    @staticmethod
    def _normalize_selection_weights(weights: Dict[str, float]) -> Dict[str, float]:
        normalized = {k: max(float(v), 0.0) for k, v in weights.items()}
        denom = sum(normalized.values())
        if denom <= 0:
            return {
                "relevance": 0.80,
                "novelty": 0.15,
                "source_diversity": 0.03,
                "hazard_diversity": 0.02,
            }
        return {k: v / denom for k, v in normalized.items()}

    @staticmethod
    def _selection_source_key(item: Dict[str, Any]) -> str:
        return str(item.get("source", "") or "").strip().lower()

    @staticmethod
    def _source_norm_factor(source_key: str, source_counts: Counter[str]) -> float:
        if not source_key:
            return 0.0
        count = max(int(source_counts.get(source_key, 0)), 1)
        return 1.0 / max(math.log1p(count), 1.0)

    @staticmethod
    def _selection_hazard_key(item: Dict[str, Any]) -> str:
        return str(item.get("hazard_type", "") or "").strip().lower()

    @staticmethod
    def _selection_family_key(item: Dict[str, Any]) -> str:
        rule_id = str(item.get("id", "") or "").strip().lower()
        if rule_id and "-" in rule_id:
            return rule_id.split("-", 1)[0]
        source_key = str(item.get("source", "") or "").strip().lower()
        return source_key.split("/", 1)[0] if source_key else ""

    def _build_candidate_token_cache(self, candidates: List[Dict[str, Any]]) -> Dict[str, set[str]]:
        token_cache: Dict[str, set[str]] = {}
        for item in candidates:
            rid = str(item.get("id", ""))
            text = " ".join(
                [
                    str(item.get("title", "")),
                    str(item.get("text", "")),
                    str(item.get("hazard_type", "")),
                    " ".join(item.get("matched_tokens", []) if isinstance(item.get("matched_tokens"), list) else []),
                ]
            )
            token_cache[rid] = set(self._tokenize(text))
        return token_cache

    def _select_mmr_evidence(
        self,
        candidates: List[Dict[str, Any]],
        limit: int,
        token_cache: Dict[str, set[str]],
    ) -> List[Dict[str, Any]]:
        mmr_lambda = max(0.0, min(float(settings.RAG_MMR_LAMBDA), 1.0))
        selected: List[Dict[str, Any]] = []
        remaining = [dict(item) for item in candidates]

        while remaining and len(selected) < limit:
            if not selected:
                best = max(remaining, key=lambda x: float(x.get("score", 0.0)))
                selected.append(best)
                remaining.remove(best)
                continue

            best_item = None
            best_score = float("-inf")
            for item in remaining:
                rid = str(item.get("id", ""))
                cand_tokens = token_cache.get(rid, set())
                similarity_penalty = 0.0
                for sel in selected:
                    sel_tokens = token_cache.get(str(sel.get("id", "")), set())
                    similarity_penalty = max(similarity_penalty, self._jaccard_similarity(cand_tokens, sel_tokens))
                mmr_score = mmr_lambda * float(item.get("score", 0.0)) - (1.0 - mmr_lambda) * similarity_penalty
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_item = item

            if not best_item:
                break
            selected.append(best_item)
            remaining.remove(best_item)

        return selected

    def _select_diverse_evidence(self, candidates: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        if not candidates or limit <= 0:
            self._last_selection_debug = {"method": "none", "selected_count": 0}
            return []
        token_cache = self._build_candidate_token_cache(candidates)
        use_set_selection = bool(settings.RAG_ENABLE_SET_SELECTION)

        if not use_set_selection:
            if not settings.RAG_ENABLE_MMR_SELECTION:
                selected = [dict(item) for item in candidates[:limit]]
                self._last_selection_debug = {
                    "method": "topk",
                    "selected_count": len(selected),
                    "candidate_count": len(candidates),
                }
                return selected
            selected = self._select_mmr_evidence(candidates, limit, token_cache)
            self._last_selection_debug = {
                "method": "mmr",
                "mmr_lambda": float(settings.RAG_MMR_LAMBDA),
                "selected_count": len(selected),
                "candidate_count": len(candidates),
            }
            return selected

        remaining = [dict(item) for item in candidates]
        selected: List[Dict[str, Any]] = []
        selected_sources: set[str] = set()
        selected_hazards: set[str] = set()
        selected_families: set[str] = set()
        max_base_score = max(float(item.get("score", 0.0)) for item in remaining) if remaining else 1.0
        source_counts = Counter(
            self._selection_source_key(rule)
            for rule in self.rules
            if self._selection_source_key(rule)
        )
        min_gain = max(float(settings.RAG_SET_SELECTION_MIN_GAIN), 0.0)
        source_norm_enabled = bool(settings.RAG_SET_SELECTION_SOURCE_NORM_ENABLED)

        weights = self._normalize_selection_weights(
            {
                "relevance": float(settings.RAG_SET_SELECTION_RELEVANCE_WEIGHT),
                "novelty": float(settings.RAG_SET_SELECTION_NOVELTY_WEIGHT),
                "source_diversity": float(settings.RAG_SET_SELECTION_SOURCE_DIVERSITY_WEIGHT),
                "hazard_diversity": float(settings.RAG_SET_SELECTION_HAZARD_DIVERSITY_WEIGHT),
            }
        )
        selection_trace: List[Dict[str, Any]] = []

        while remaining and len(selected) < limit:
            best_item: Dict[str, Any] | None = None
            best_score = float("-inf")
            best_components: Dict[str, float] = {}

            for item in remaining:
                rid = str(item.get("id", ""))
                base_score = float(item.get("score", 0.0))
                relevance = base_score / max_base_score if max_base_score > 0 else 0.0

                novelty = 1.0
                if selected:
                    cand_tokens = token_cache.get(rid, set())
                    max_similarity = 0.0
                    for sel in selected:
                        sel_tokens = token_cache.get(str(sel.get("id", "")), set())
                        max_similarity = max(max_similarity, self._jaccard_similarity(cand_tokens, sel_tokens))
                    novelty = 1.0 - max_similarity

                source_key = self._selection_source_key(item)
                hazard_key = self._selection_hazard_key(item)
                family_key = self._selection_family_key(item)
                source_norm = 0.0
                source_diversity = 0.0
                if source_key and source_key not in selected_sources:
                    source_norm = self._source_norm_factor(source_key, source_counts) if source_norm_enabled else 1.0
                    source_diversity = source_norm
                hazard_diversity = 1.0 if hazard_key and hazard_key not in selected_hazards else 0.0
                family_penalty_value = max(float(settings.RAG_SET_SELECTION_FAMILY_REPEAT_PENALTY), 0.0)
                family_penalty = family_penalty_value if family_key and family_key in selected_families else 0.0

                set_score = (
                    weights["relevance"] * relevance
                    + weights["novelty"] * novelty
                    + weights["source_diversity"] * source_diversity
                    + weights["hazard_diversity"] * hazard_diversity
                    - family_penalty
                )

                if set_score > best_score:
                    best_score = set_score
                    best_item = item
                    best_components = {
                        "relevance": round(relevance, 4),
                        "novelty": round(novelty, 4),
                        "source_diversity": round(source_diversity, 4),
                        "source_norm": round(source_norm, 4),
                        "hazard_diversity": round(hazard_diversity, 4),
                        "family_penalty": round(family_penalty, 4),
                    }

            if not best_item:
                break
            if selected and best_score <= min_gain:
                break

            picked = dict(best_item)
            picked["selection_score"] = round(best_score, 4)
            picked["selection_components"] = best_components
            selected.append(picked)
            remaining.remove(best_item)

            source_key = self._selection_source_key(best_item)
            hazard_key = self._selection_hazard_key(best_item)
            family_key = self._selection_family_key(best_item)
            if source_key:
                selected_sources.add(source_key)
            if hazard_key:
                selected_hazards.add(hazard_key)
            if family_key:
                selected_families.add(family_key)

            selection_trace.append(
                {
                    "id": str(best_item.get("id", "")),
                    "score": round(best_score, 4),
                    "source_key": source_key,
                    "hazard_key": hazard_key,
                    "family_key": family_key,
                    "components": best_components,
                }
            )

        self._last_selection_debug = {
            "method": "set_selection",
            "weights": {k: round(v, 4) for k, v in weights.items()},
            "selected_count": len(selected),
            "candidate_count": len(candidates),
            "min_gain": round(min_gain, 4),
            "source_norm_enabled": source_norm_enabled,
            "source_coverage": len(selected_sources),
            "hazard_coverage": len(selected_hazards),
            "trace": selection_trace[:8],
        }
        return selected

    def retrieve_with_debug(
        self,
        query: str,
        scene: str,
        top_k: int | None = None,
        min_score: float | None = None,
        min_token_hits: int | None = None,
    ) -> Dict[str, Any]:
        if top_k is None:
            top_k = settings.RAG_TOP_K
        requested_top_k = max(int(top_k), 1)
        if min_score is None:
            min_score = settings.RAG_MIN_SCORE
        if min_token_hits is None:
            min_token_hits = settings.RAG_MIN_TOKEN_HITS

        mode = str(settings.RAG_RETRIEVAL_MODE or "hybrid").strip().lower()
        min_vector_score = float(settings.RAG_MIN_VECTOR_SCORE)
        min_dense_score = float(settings.RAG_MIN_DENSE_SCORE)
        api_key = self._get_api_key()
        dense_enabled = bool(settings.RAG_ENABLE_DENSE_RETRIEVAL and api_key)

        prepared = self._prepare_queries(query, scene)
        query_budget_result = self._apply_dynamic_query_budget(prepared)
        retrieval_queries = query_budget_result.get("queries", [])
        hazard_hints = self._infer_hazard_hints(
            " ".join(
                [
                    str(prepared.get("original_query", "")),
                    str(prepared.get("rewrite", "")),
                    str(query or ""),
                ]
            )
        )
        effective_top_k = requested_top_k
        if settings.RAG_ENABLE_DYNAMIC_TOP_K:
            query_complexity = (
                len(retrieval_queries)
                + len(prepared.get("multi_queries", []))
                + len(prepared.get("sub_questions", []))
            )
            top_k_cap = max(int(settings.RAG_TOP_K_MAX), requested_top_k)
            if query_complexity >= 8:
                effective_top_k = min(max(requested_top_k, 5), top_k_cap)
            elif query_complexity >= 6:
                effective_top_k = min(max(requested_top_k, 4), top_k_cap)

        query_weights = {
            "original": 1.0,
            "rewrite": 1.03,
            "scene_query": 1.01,
            "hazard_branch": 1.05,
            "multi_query": 0.96,
            "sub_question": 0.93,
        }

        scored_map: Dict[str, Dict[str, Any]] = {}
        query_debug: List[Dict[str, Any]] = []

        for query_item in retrieval_queries:
            query_text = query_item["text"]
            query_kind = query_item["kind"]
            query_path = str(query_item.get("path", "root"))
            query_depth = int(query_item.get("depth", 0) or 0)
            query_branch = str(query_item.get("branch", "root"))
            expanded_query = self._expand_query(query_text)
            query_tokens = self._tokenize(expanded_query)
            query_vec = self._tfidf_vector(query_tokens, self._idf)
            query_norm = self._norm(query_vec)
            dense_scores = self._compute_dense_scores(api_key, expanded_query) if dense_enabled else {}

            query_debug.append(
                {
                    "kind": query_kind,
                    "query": query_text,
                    "path": query_path,
                    "depth": query_depth,
                    "branch": query_branch,
                    "expanded_query": expanded_query,
                    "token_count": len(query_tokens),
                    "vector_dims": len(query_vec),
                    "dense_enabled": bool(dense_scores),
                }
            )

            for idx, rule in enumerate(self.rules):
                score_info = self._score_rule(
                    rule_idx=idx,
                    rule=rule,
                    query_tokens=query_tokens,
                    query_vec=query_vec,
                    query_norm=query_norm,
                    scene=scene,
                )

                rule_id = str(rule.get("id", ""))
                dense_score_raw = float(dense_scores.get(rule_id, 0.0))
                dense_score_norm = self._normalize_dense_score(dense_score_raw) if dense_scores else 0.0
                combined_score = self._blend_retrieval_score(score_info["final_score"], dense_score_norm)
                hazard_bonus = self._hazard_hint_bonus(rule, hazard_hints)
                if hazard_bonus > 0:
                    combined_score += hazard_bonus
                weighted_score = round(float(combined_score) * float(query_weights.get(query_kind, 1.0)), 6)

                lexical_pass_strict = (
                    score_info["token_hits"] >= int(min_token_hits)
                    and score_info["lexical_score"] >= float(min_score)
                )
                lexical_pass_loose = score_info["token_hits"] >= int(min_token_hits)
                vector_pass = score_info["vector_score"] >= min_vector_score
                dense_pass = bool(dense_scores) and dense_score_raw >= min_dense_score

                if mode == "keyword":
                    if not lexical_pass_strict:
                        continue
                elif mode == "vector":
                    if not (vector_pass or dense_pass):
                        continue
                else:
                    if not (lexical_pass_loose or vector_pass or dense_pass):
                        continue

                existing = scored_map.get(rule_id)
                if not existing:
                    scored_map[rule_id] = {
                        "id": rule_id,
                        "source": rule.get("source", ""),
                        "article": rule.get("article", ""),
                        "title": rule.get("title", ""),
                        "text": rule.get("text", ""),
                        "hazard_type": rule.get("hazard_type", ""),
                        "score": round(weighted_score, 4),
                        "lexical_score": round(score_info["lexical_score"], 4),
                        "vector_score": round(score_info["vector_score"], 4),
                        "dense_score_raw": round(dense_score_raw, 4),
                        "dense_score_norm": round(dense_score_norm, 4),
                        "hazard_bonus": round(hazard_bonus, 4),
                        "token_hits": score_info["token_hits"],
                        "matched_tokens": score_info["matched_tokens"][:12],
                        "scene_match": score_info["scene_match"],
                        "best_query": query_text,
                        "best_query_kind": query_kind,
                        "best_query_path": query_path,
                        "best_query_branch": query_branch,
                        "matched_query_count": 1,
                        "matched_queries": [query_text],
                        "matched_query_kinds": [query_kind],
                        "matched_paths": [query_path],
                        "matched_branches": [query_branch],
                        "path_scores": {query_path: round(weighted_score, 4)},
                    }
                    continue

                if query_text.lower() not in {x.lower() for x in existing.get("matched_queries", [])}:
                    existing["matched_query_count"] = int(existing.get("matched_query_count", 0)) + 1
                    existing.setdefault("matched_queries", []).append(query_text)
                    existing.setdefault("matched_query_kinds", []).append(query_kind)
                if query_path and query_path not in existing.get("matched_paths", []):
                    existing.setdefault("matched_paths", []).append(query_path)
                if query_branch and query_branch not in existing.get("matched_branches", []):
                    existing.setdefault("matched_branches", []).append(query_branch)
                path_scores = existing.setdefault("path_scores", {})
                if isinstance(path_scores, dict):
                    prev_path_score = float(path_scores.get(query_path, 0.0))
                    if weighted_score > prev_path_score:
                        path_scores[query_path] = round(weighted_score, 4)

                if weighted_score > float(existing.get("score", 0.0)):
                    existing.update(
                        {
                            "score": round(weighted_score, 4),
                            "lexical_score": round(score_info["lexical_score"], 4),
                            "vector_score": round(score_info["vector_score"], 4),
                            "dense_score_raw": round(dense_score_raw, 4),
                            "dense_score_norm": round(dense_score_norm, 4),
                            "hazard_bonus": round(hazard_bonus, 4),
                            "token_hits": score_info["token_hits"],
                            "matched_tokens": score_info["matched_tokens"][:12],
                            "scene_match": score_info["scene_match"],
                            "best_query": query_text,
                            "best_query_kind": query_kind,
                            "best_query_path": query_path,
                            "best_query_branch": query_branch,
                        }
                    )

        scored = list(scored_map.values())
        scored.sort(
            key=lambda x: (
                float(x.get("score", 0.0)),
                int(x.get("matched_query_count", 0)),
                float(x.get("dense_score_raw", 0.0)),
                float(x.get("vector_score", 0.0)),
                float(x.get("lexical_score", 0.0)),
                int(x.get("token_hits", 0)),
            ),
            reverse=True,
        )

        rerank_query = prepared.get("rewrite") or prepared.get("original_query") or query
        rerank_debug = self._apply_rerank(api_key, rerank_query, scored)
        if rerank_debug.get("applied"):
            scored = rerank_debug.get("results", scored)

        evidence_tree_enabled = bool(settings.RAG_ENABLE_EVIDENCE_TREE_SEARCH)
        aggregate_paths = bool(settings.RAG_EVIDENCE_TREE_AGGREGATE_PATHS)
        max_path_bonus = max(float(settings.RAG_EVIDENCE_TREE_PATH_BONUS), 0.0)
        for item in scored:
            path_scores_raw = item.get("path_scores", {})
            if not isinstance(path_scores_raw, dict):
                path_scores_raw = {}
            branches: set[str] = set()
            for path_key in path_scores_raw.keys():
                path_value = str(path_key or "").strip().lower()
                if not path_value:
                    continue
                parts = path_value.split("/", 2)
                branch = parts[1] if len(parts) >= 2 else "root"
                branches.add(branch)
            path_count = len(path_scores_raw)
            branch_count = len(branches)
            path_score_values: List[float] = []
            for raw_value in path_scores_raw.values():
                try:
                    path_score_values.append(float(raw_value))
                except (TypeError, ValueError):
                    continue
            best_path_score = max(path_score_values) if path_score_values else float(item.get("score", 0.0))
            tree_path_score = sum(path_score_values) if path_score_values else best_path_score
            base_score = float(item.get("score", 0.0))
            if evidence_tree_enabled and aggregate_paths and path_score_values:
                base_score = tree_path_score
                rerank_norm = float(item.get("rerank_score_norm", 0.0) or 0.0)
                if rerank_norm > 0:
                    rerank_weight = max(0.0, min(float(settings.RAG_RERANK_WEIGHT), 0.98))
                    base_score = (1.0 - rerank_weight) * base_score + rerank_weight * rerank_norm
            path_bonus = 0.0
            if evidence_tree_enabled and path_count > 1 and max_path_bonus > 0:
                support_term = min(path_count, 4) / 4.0
                branch_term = min(branch_count, 3) / 3.0
                path_bonus = round(max_path_bonus * (0.6 * support_term + 0.4 * branch_term), 4)
            item["score"] = round(base_score + path_bonus, 4)
            item["path_count"] = path_count
            item["branch_count"] = branch_count
            item["best_path_score"] = round(best_path_score, 4)
            item["tree_path_score"] = round(tree_path_score, 4)
            item["path_bonus"] = round(path_bonus, 4)
            if path_scores_raw:
                best_path = max(path_scores_raw.items(), key=lambda kv: float(kv[1]))[0]
                item["best_path"] = str(best_path)

        scored.sort(
            key=lambda x: (
                float(x.get("score", 0.0)),
                int(x.get("matched_query_count", 0)),
                float(x.get("path_bonus", 0.0)),
                float(x.get("dense_score_raw", 0.0)),
                float(x.get("vector_score", 0.0)),
                float(x.get("lexical_score", 0.0)),
                int(x.get("token_hits", 0)),
            ),
            reverse=True,
        )

        deduped: List[Dict[str, Any]] = []
        seen_keys = set()
        candidate_limit = max(
            effective_top_k * max(int(settings.RAG_MMR_CANDIDATE_MULTIPLIER), 1),
            effective_top_k,
        )
        for item in scored:
            key = str(item.get("id", "")).strip()
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(item)
            if len(deduped) >= candidate_limit:
                break

        selected = self._select_diverse_evidence(deduped, effective_top_k)
        selected_path_summary = [
            {
                "id": str(item.get("id", "")),
                "best_path": str(item.get("best_path", item.get("best_query_path", ""))),
                "path_count": int(item.get("path_count", 0) or 0),
                "branch_count": int(item.get("branch_count", 0) or 0),
                "path_bonus": float(item.get("path_bonus", 0.0) or 0.0),
                "best_path_score": float(item.get("best_path_score", 0.0) or 0.0),
                "tree_path_score": float(item.get("tree_path_score", 0.0) or 0.0),
            }
            for item in selected[:8]
        ]

        return {
            "rules": selected,
            "debug": {
                "query": query,
                "rewrite": prepared.get("rewrite", ""),
                "multi_queries": prepared.get("multi_queries", []),
                "sub_questions": prepared.get("sub_questions", []),
                "retrieval_queries": query_debug,
                "query_budget": query_budget_result.get("debug", {}),
                "query_strategy": prepared.get("strategy", "heuristic"),
                "evidence_tree": {
                    "enabled": bool(settings.RAG_ENABLE_EVIDENCE_TREE_SEARCH),
                    "aggregate_paths": bool(settings.RAG_EVIDENCE_TREE_AGGREGATE_PATHS),
                    "config_path_bonus": float(settings.RAG_EVIDENCE_TREE_PATH_BONUS),
                    "config_hazard_branch_max": int(settings.RAG_EVIDENCE_TREE_HAZARD_BRANCH_MAX),
                    "tree": prepared.get("query_tree", {}),
                    "selected_paths": selected_path_summary,
                },
                "scene": scene,
                "retrieval_mode": mode,
                "candidate_count": len(scored),
                "returned_count": len(selected),
                "thresholds": {
                    "top_k": requested_top_k,
                    "effective_top_k": effective_top_k,
                    "candidate_limit": candidate_limit,
                    "min_score": min_score,
                    "min_token_hits": min_token_hits,
                    "min_vector_score": min_vector_score,
                    "min_dense_score": min_dense_score,
                },
                "weights": {
                    "lexical": float(settings.RAG_LEXICAL_WEIGHT),
                    "vector": float(settings.RAG_VECTOR_WEIGHT),
                    "dense": float(settings.RAG_DENSE_WEIGHT),
                    "rerank": float(settings.RAG_RERANK_WEIGHT),
                    "scene_bonus": float(settings.RAG_SCENE_BONUS),
                    "query_kind": query_weights,
                },
                "selection": {
                    "dynamic_top_k": bool(settings.RAG_ENABLE_DYNAMIC_TOP_K),
                    "mmr_enabled": bool(settings.RAG_ENABLE_MMR_SELECTION),
                    "mmr_lambda": float(settings.RAG_MMR_LAMBDA),
                    "set_selection_enabled": bool(settings.RAG_ENABLE_SET_SELECTION),
                    "set_selection_weights": {
                        "relevance": float(settings.RAG_SET_SELECTION_RELEVANCE_WEIGHT),
                        "novelty": float(settings.RAG_SET_SELECTION_NOVELTY_WEIGHT),
                        "source_diversity": float(settings.RAG_SET_SELECTION_SOURCE_DIVERSITY_WEIGHT),
                        "hazard_diversity": float(settings.RAG_SET_SELECTION_HAZARD_DIVERSITY_WEIGHT),
                    },
                    "set_selection_min_gain": float(settings.RAG_SET_SELECTION_MIN_GAIN),
                    "source_norm_enabled": bool(settings.RAG_SET_SELECTION_SOURCE_NORM_ENABLED),
                    "hazard_hint_routing": bool(settings.RAG_ENABLE_HAZARD_HINT_ROUTING),
                    "hazard_hint_bonus": float(settings.RAG_HAZARD_HINT_BONUS),
                    "hazard_hints": sorted(hazard_hints),
                    "selector_debug": self._last_selection_debug,
                },
                "dense": {
                    "enabled": bool(settings.RAG_ENABLE_DENSE_RETRIEVAL),
                    "active": dense_enabled,
                    "model": settings.RAG_EMBEDDING_MODEL,
                    "cache_hit": self._dense_cache_hit,
                    "index_ready": self._dense_index_ready,
                },
                "rerank": {
                    "enabled": bool(settings.RAG_ENABLE_RERANK),
                    "applied": bool(rerank_debug.get("applied")),
                    "model": settings.RAG_RERANK_MODEL,
                    "top_n": int(rerank_debug.get("rerank_top_n", 0) or 0),
                    "error": rerank_debug.get("error", ""),
                },
                "knowledge_base": self.meta,
            },
        }

    def retrieve(self, query: str, scene: str, top_k: int = 5) -> List[Dict[str, Any]]:
        result = self.retrieve_with_debug(query=query, scene=scene, top_k=top_k)
        return result["rules"]


rule_retriever = RuleRetriever()
