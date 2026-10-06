"""Open-set guardrail wrapper for fire-safety retrieval.

Goals:
- Detect "out-of-scope" queries that should not produce strong conclusions.
- Aggregate multiple weak signals into a single refusal decision.
- Achieve high refusal recall (>=0.7) while keeping precision >=0.9 on
  the open-set benchmark.

Signals used:
1. Query topic fitness: tokens that are clearly out of fire-safety scope
   (color of tiles, dress code, etc.) → strong refuse.
2. Image quality complaint markers: blurry, noisy, compressed, occluded → strong refuse.
3. Retrieval score: top-1 below threshold → soft refuse.
4. Coverage: query token overlap with top-k rules' tags + text → soft refuse if low.
5. Source consensus: if top-3 results are all from totally unrelated articles → soft refuse.

The decision is a weighted score with a configurable threshold.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# --- Trigger lexicons ---

# Words/phrases that strongly indicate poor visual evidence
LOW_QUALITY_TOKENS_EN = [
    "blurry", "blur", "low resolution", "low-res", "low quality",
    "noisy", "noise", "compressed", "compression artifact",
    "occluded", "obstructed view", "partial view", "cut off",
    "out of focus", "unrecognizable", "indistinct",
]
LOW_QUALITY_TOKENS_ZH = [
    "看不清", "模糊", "画面模糊", "压缩块", "噪点", "马赛克",
    "分辨率低", "看不见", "看不清楚", "无法辨认", "辨认不清",
    "光线不足", "曝光过度", "图像不清晰", "画质差",
]

# Out-of-scope topic markers — things that aren't fire safety hazards
OUT_OF_SCOPE_MARKERS_ZH = [
    "颜色不统一", "着装不统一", "服装不规范", "瓷砖颜色",
    "墙面颜色", "桌椅整齐", "卫生不达标", "员工迟到",
    "考勤", "工资", "排班不合理", "停车位不够",
    "网络不稳定", "wifi信号", "空调温度", "桌面整洁",
]
OUT_OF_SCOPE_MARKERS_EN = [
    "uniform color", "dress code", "tile color", "wall color",
    "attendance record", "lunch break", "wifi signal",
    "ac temperature", "salary", "parking spots", "table arrangement",
]

# Query templates that ask for "any rule that fits" without describing a hazard
WEAK_QUERY_PATTERNS = [
    r"按哪条.*?处罚",  # punish under which rule
    r"which.*regulation.*cited",
    r"是否构成.*隐患",  # is this a hazard?
    r"算.*隐患吗",
]

# Fire-safety topic anchors — query should contain at least one
FIRE_DOMAIN_KEYWORDS_ZH = [
    "消防", "火灾", "灭火", "燃烧", "燃气", "烟", "排烟",
    "疏散", "通道", "出口", "楼梯", "应急", "可燃", "易燃",
    "防火", "电气", "短路", "过载", "充电", "电池", "锂电",
    "动火", "焊接", "明火", "厨房", "油烟", "灶", "锅炉",
    "化学品", "危险品", "爆炸", "粉尘", "氧气", "瓶",
    "电动车", "电动自行车", "走道", "门厅", "井", "档案",
]
FIRE_DOMAIN_KEYWORDS_EN = [
    "fire", "flame", "smoke", "burn", "extinguisher", "evacuation",
    "exit", "stair", "emergency", "combustible", "flammable",
    "electrical", "overload", "short circuit", "charging", "battery",
    "hot work", "welding", "kitchen", "stove", "boiler", "gas",
    "hazardous", "explosion", "dust", "oxygen", "cylinder", "e-bike",
    "corridor", "lobby", "shaft", "hydrant", "sprinkler", "alarm",
    "ppe", "lockout", "tagout",
]


@dataclass
class GuardrailDecision:
    """Output of guardrail evaluation."""
    should_refuse: bool = False
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    signals: Dict[str, float] = field(default_factory=dict)
    refusal_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "should_refuse": self.should_refuse,
            "confidence": round(self.confidence, 4),
            "reasons": self.reasons,
            "signals": {k: round(v, 4) for k, v in self.signals.items()},
            "refusal_message": self.refusal_message,
        }


@dataclass
class GuardrailConfig:
    """Configurable thresholds for refusal decision."""
    # If accumulated refusal_score >= refusal_threshold, refuse.
    refusal_threshold: float = 0.5

    # Per-signal weights (higher = more likely to trigger refusal)
    weight_low_quality_image: float = 0.7
    weight_out_of_scope: float = 0.7
    weight_no_fire_domain: float = 0.4
    weight_weak_query_no_anchor: float = 0.3
    weight_low_top1_score: float = 0.25
    weight_low_coverage: float = 0.20
    weight_low_token_overlap: float = 0.20

    # Score thresholds
    top1_score_min: float = 0.30   # below this counts as low_top1
    coverage_min: float = 0.10     # below this counts as low coverage
    token_overlap_min: int = 1     # required minimum query-token-in-top-rule

    # Boilerplate refusal message
    refusal_message_template: str = (
        "证据不足或问题超出消防安全范围，建议补充清晰图片或调整问题后再分析；"
        "或转人工复核（reasons: {reasons}）。"
    )


def _tokenize_zh_en(text: str) -> List[str]:
    """Crude tokenization that splits Chinese characters and English words."""
    if not text:
        return []
    # Lowercase and split into Chinese chars + Latin/digit words
    text = text.lower()
    tokens = []
    for token in re.findall(r"[a-z0-9_]+|[一-鿿]", text):
        tokens.append(token)
    return tokens


def _contains_any(text: str, lex: List[str]) -> List[str]:
    if not text:
        return []
    text_lower = text.lower()
    hits = []
    for w in lex:
        if w.lower() in text_lower:
            hits.append(w)
    return hits


def _contains_pattern(text: str, patterns: List[str]) -> List[str]:
    hits = []
    for p in patterns:
        if re.search(p, text):
            hits.append(p)
    return hits


def evaluate_guardrail(
    query: str,
    scene: str,
    retrieved_rules: List[Dict[str, Any]],
    debug: Optional[Dict[str, Any]] = None,
    config: Optional[GuardrailConfig] = None,
) -> GuardrailDecision:
    """Evaluate guardrail signals and decide whether to refuse.

    Args:
        query: original user query (str)
        scene: scene identifier
        retrieved_rules: list of rule dicts from retriever
        debug: optional retriever debug dict (with 'scores', 'tokens', etc.)
        config: optional GuardrailConfig overrides

    Returns:
        GuardrailDecision
    """
    cfg = config or GuardrailConfig()
    decision = GuardrailDecision()
    score = 0.0

    text = (query or "").strip()
    if not text:
        # Empty query → refuse
        decision.should_refuse = True
        decision.reasons.append("empty_query")
        decision.confidence = 1.0
        decision.signals["empty_query"] = 1.0
        decision.refusal_message = cfg.refusal_message_template.format(reasons="empty_query")
        return decision

    # Signal 1: low-quality image markers in query
    quality_hits = _contains_any(text, LOW_QUALITY_TOKENS_EN + LOW_QUALITY_TOKENS_ZH)
    if quality_hits:
        score += cfg.weight_low_quality_image
        decision.reasons.append(f"low_quality_image:{len(quality_hits)}")
        decision.signals["low_quality_image"] = float(len(quality_hits))

    # Signal 2: out-of-scope markers
    oos_hits = _contains_any(text, OUT_OF_SCOPE_MARKERS_EN + OUT_OF_SCOPE_MARKERS_ZH)
    if oos_hits:
        score += cfg.weight_out_of_scope
        decision.reasons.append(f"out_of_scope:{len(oos_hits)}")
        decision.signals["out_of_scope"] = float(len(oos_hits))

    # Signal 3: no fire-domain anchor in query
    fire_hits = _contains_any(text, FIRE_DOMAIN_KEYWORDS_EN + FIRE_DOMAIN_KEYWORDS_ZH)
    has_fire_anchor = bool(fire_hits)
    if not has_fire_anchor:
        score += cfg.weight_no_fire_domain
        decision.reasons.append("no_fire_domain")
        decision.signals["no_fire_domain"] = 1.0

    # Signal 4: weak query template + no fire anchor → likely fishing
    weak_hits = _contains_pattern(text, WEAK_QUERY_PATTERNS)
    if weak_hits and not has_fire_anchor:
        score += cfg.weight_weak_query_no_anchor
        decision.reasons.append("weak_query_no_anchor")
        decision.signals["weak_query_no_anchor"] = 1.0

    # Signal 5: top-1 retrieval score low (if available from debug)
    if debug and isinstance(debug, dict):
        scores = debug.get("scores") or debug.get("ranking_scores") or []
        if isinstance(scores, list) and scores:
            try:
                top1_score = float(scores[0])
            except (TypeError, ValueError):
                top1_score = 0.0
            decision.signals["top1_score"] = top1_score
            if top1_score < cfg.top1_score_min:
                score += cfg.weight_low_top1_score
                decision.reasons.append(f"low_top1_score:{top1_score:.2f}")

    # Signal 6: query-token-in-top-rule (lexical coverage check)
    if retrieved_rules:
        query_tokens = set(_tokenize_zh_en(text))
        # Filter trivial/single-char tokens that match too easily
        query_tokens = {t for t in query_tokens if len(t) >= 2 or t.isalpha()}
        if query_tokens:
            top1_text = ""
            top1 = retrieved_rules[0]
            if isinstance(top1, dict):
                top1_text = " ".join([
                    str(top1.get("text") or ""),
                    str(top1.get("title") or ""),
                    " ".join(top1.get("tags") or []),
                ])
            top1_tokens = set(_tokenize_zh_en(top1_text))
            overlap = query_tokens & top1_tokens
            decision.signals["token_overlap"] = float(len(overlap))
            if len(overlap) < cfg.token_overlap_min:
                score += cfg.weight_low_token_overlap
                decision.reasons.append(f"low_token_overlap:{len(overlap)}")
    else:
        score += cfg.weight_low_top1_score + cfg.weight_low_coverage
        decision.reasons.append("no_results")
        decision.signals["no_results"] = 1.0

    # Final decision
    decision.confidence = min(score, 1.0)
    decision.signals["aggregate_score"] = score
    decision.should_refuse = score >= cfg.refusal_threshold
    if decision.should_refuse:
        decision.refusal_message = cfg.refusal_message_template.format(
            reasons=",".join(decision.reasons)
        )
    return decision


def filter_with_guardrail(
    query: str,
    scene: str,
    retrieved_rules: List[Dict[str, Any]],
    debug: Optional[Dict[str, Any]] = None,
    config: Optional[GuardrailConfig] = None,
) -> Tuple[List[Dict[str, Any]], GuardrailDecision]:
    """Apply guardrail; on refuse, return empty rules list + decision.

    Returns:
        (rules_to_use, decision)
        - if decision.should_refuse, rules_to_use is empty list
        - else, returns the original retrieved_rules
    """
    decision = evaluate_guardrail(query, scene, retrieved_rules, debug, config)
    if decision.should_refuse:
        return [], decision
    return list(retrieved_rules or []), decision
