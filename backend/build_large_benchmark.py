#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parent
DEFAULT_BASE = ROOT / "retrieval_benchmark_v2.json"
DEFAULT_RULES = ROOT / "app" / "data" / "fire_rules.json"
DEFAULT_MANIFEST = ROOT / "app" / "data" / "public_testsets_manifest.json"
DEFAULT_OUT = ROOT / "retrieval_benchmark_large_v1.json"
DEFAULT_OPEN_SET_OUT = ROOT / "retrieval_benchmark_open_set_v1.json"

SCENE_TEXT = {
    "campus": "校园",
    "dormitory": "宿舍",
    "office": "办公楼",
    "residential": "居民区",
    "factory": "工厂",
    "industrial": "工业现场",
    "construction": "工地",
    "warehouse": "仓储区",
}

HARD_DISTRACTORS = [
    "另外有人提到演练台账可能不完整。",
    "旁边同事还问了应急预案更新频率。",
    "管理层还关心培训记录是否齐全。",
    "顺便还想确认日常巡检是否达标。",
    "另有反馈说设备维护档案需要复核。",
]

POSITIVE_TEMPLATES = [
    "{scene_text}现场发现{hazard_phrase}，对应哪些消防条款？",
    "请按法规审查：{scene_text}里{hazard_phrase}，给出依据。",
    "在{scene_text}场景，{hazard_phrase}是否违规？请列出关键条款。",
    "你是消防审查员。图像描述显示{hazard_phrase}，请返回法规依据与处置建议。",
    "Risk check for {scene}: {hazard_phrase_en}. Please cite Chinese fire safety rules.",
    "请先给结论再给依据：{scene_text}出现{hazard_phrase}，该如何整改？",
    "作为安全负责人，我需要确认{scene_text}中{hazard_phrase}的合规性。",
]

SEED_AUG_PREFIX = [
    "请进行法规核查：",
    "请用审计视角回答：",
    "请按隐患闭环管理要求判断：",
]

SEED_AUG_SUFFIX = [
    "并给出最小整改动作。",
    "如果证据不足请明确说明。",
    "请只输出最关键的1-2条依据。",
]

OPEN_SET_TEMPLATES = [
    "{scene_text}里宣传海报配色太暗，是否属于消防违法？",
    "{scene_text}监控画面有噪点和压缩块，需要按哪条消防法规处罚？",
    "{scene_text}地面瓷砖颜色不统一，这算消防隐患吗？",
    "{scene_text}墙面装饰风格太老旧，是否违反消防法？",
    "{scene_text}人员着装不统一，能否直接按消防条款处罚？",
    "The {scene} area has blurry camera quality only. Which fire regulation must be cited?",
]

HAZARD_PHRASE_ZH = {
    "extinguisher_blocked": "灭火器被杂物遮挡",
    "evacuation_obstructed": "疏散通道被占用",
    "signage_missing_or_blocked": "安全出口指示被遮挡",
    "extinguisher_invalid": "灭火器压力异常或失效",
    "electrical_overload_or_aging": "电气线路过载或老化",
    "multi_device_one_box": "同一开关箱控制多台设备",
    "combustible_near_heat_source": "可燃物靠近热源",
    "sprinkler_blocked_or_damaged": "喷淋喷头被遮挡或损坏",
    "fire_door_nonfunctional": "防火门常开或闭门器失效",
    "hydrant_blocked": "消火栓前方被堆物占用",
    "fire_lane_occupied": "消防车通道被占用",
    "alarm_fault_or_disabled": "火灾报警系统故障或停用",
}

HAZARD_PHRASE_EN = {
    "extinguisher_blocked": "fire extinguisher blocked by objects",
    "evacuation_obstructed": "evacuation route blocked",
    "signage_missing_or_blocked": "exit signage blocked or missing",
    "extinguisher_invalid": "extinguisher out of service",
    "electrical_overload_or_aging": "overloaded or aging electrical wiring",
    "multi_device_one_box": "multiple devices powered by one switch box",
    "combustible_near_heat_source": "combustible materials near heat source",
    "sprinkler_blocked_or_damaged": "sprinkler blocked or damaged",
    "fire_door_nonfunctional": "fire door not functioning",
    "hydrant_blocked": "hydrant access blocked",
    "fire_lane_occupied": "fire lane occupied",
    "alarm_fault_or_disabled": "fire alarm fault or disabled",
}

DATASET_SIGNAL_MAPPINGS = {
    "fire_smoke_visible": ["FIRELAW-16", "FIRELAW-28"],
    "combustible_near_heat_source": ["GB50016-3.3.8"],
    "electrical_overload_or_aging": ["GB50016-10.2.7"],
    "construction_site_compliance": ["IND-POWER-001"],
    "industrial_operation_risk": ["IND-POWER-001", "GB50016-10.2.7"],
    "equipment_visibility_and_occlusion": ["GB50016-8.4.1", "GB50016-10.1.5", "GB50016-10.3.1"],
    "scene_observation_to_risk_reasoning": ["FIRELAW-16", "GB50016-10.2.7", "GB50016-3.3.8"],
}


def _safe_text(value: Any, default: str = "") -> str:
    text = str(value or default)
    return re.sub(r"\s+", " ", text).strip()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_seed_cases(path: Path) -> List[Dict[str, Any]]:
    raw = load_json(path)
    if not isinstance(raw, list):
        raise ValueError(f"seed benchmark must be list: {path}")
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        query = _safe_text(item.get("query"))
        scene = _safe_text(item.get("scene"), "campus") or "campus"
        expected_ids = [_safe_text(x) for x in item.get("expected_ids", []) if _safe_text(x)]
        if not query or not expected_ids:
            continue
        out.append(
            {
                "name": _safe_text(item.get("name"), f"seed_{len(out)}"),
                "scene": scene,
                "query": query,
                "expected_ids": expected_ids,
                "difficulty": "seed",
                "source": "seed_benchmark",
            }
        )
    return out


def load_rules(path: Path) -> List[Dict[str, Any]]:
    raw = load_json(path)
    rules = raw.get("rules", []) if isinstance(raw, dict) else []
    out: List[Dict[str, Any]] = []
    for item in rules:
        if not isinstance(item, dict):
            continue
        rule_id = _safe_text(item.get("id"))
        hazard_type = _safe_text(item.get("hazard_type"))
        if not rule_id:
            continue
        scenes = [
            _safe_text(s)
            for s in item.get("scene", [])
            if _safe_text(s)
        ]
        if not scenes:
            scenes = ["campus"]
        out.append(
            {
                "id": rule_id,
                "hazard_type": hazard_type,
                "title": _safe_text(item.get("title")),
                "tags": [_safe_text(t) for t in item.get("tags", []) if _safe_text(t)],
                "scene": scenes,
            }
        )
    if not out:
        raise ValueError(f"no rules loaded from {path}")
    return out


def _hazard_phrase(rule: Dict[str, Any]) -> tuple[str, str]:
    hazard = _safe_text(rule.get("hazard_type"))
    zh = HAZARD_PHRASE_ZH.get(hazard)
    en = HAZARD_PHRASE_EN.get(hazard)
    if zh and en:
        return zh, en

    title = _safe_text(rule.get("title"))
    tags = [t for t in rule.get("tags", []) if t]
    if not zh:
        zh_candidates = [t for t in tags if re.search(r"[\u4e00-\u9fff]", t)]
        zh = zh_candidates[0] if zh_candidates else title or hazard.replace("_", " ")
    if not en:
        en_candidates = [t for t in tags if not re.search(r"[\u4e00-\u9fff]", t)]
        en = en_candidates[0] if en_candidates else title.lower() or hazard.replace("_", " ")
    return zh, en


def build_large_cases(
    seed_cases: List[Dict[str, Any]],
    rules: List[Dict[str, Any]],
    manifest: Dict[str, Any],
    target_size: int,
    seed: int,
) -> List[Dict[str, Any]]:
    rng = random.Random(seed)

    rules_by_hazard: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    rules_by_id: Dict[str, Dict[str, Any]] = {}
    for rule in rules:
        rules_by_hazard[_safe_text(rule.get("hazard_type"), "unknown")].append(rule)
        rules_by_id[rule["id"]] = rule

    cases: List[Dict[str, Any]] = list(seed_cases)

    # Seed-driven augmentation
    for idx, seed_case in enumerate(seed_cases):
        scene = _safe_text(seed_case.get("scene"), "campus")
        query = _safe_text(seed_case.get("query"))
        expected_ids = list(seed_case.get("expected_ids", []))
        if not query or not expected_ids:
            continue
        for v in range(2):
            aug_query = (
                f"{SEED_AUG_PREFIX[(idx + v) % len(SEED_AUG_PREFIX)]}"
                f"{query} {SEED_AUG_SUFFIX[(idx + v) % len(SEED_AUG_SUFFIX)]}"
            )
            if v == 1:
                aug_query += " Also include one short English rationale."
            cases.append(
                {
                    "name": f"{seed_case.get('name', f'seed_{idx}')}_aug_{v}",
                    "scene": scene,
                    "query": aug_query,
                    "expected_ids": expected_ids,
                    "difficulty": "hard" if v == 0 else "blind",
                    "source": "seed_augmentation",
                }
            )

    # Rule-driven expansion
    for rule in rules:
        siblings = [r["id"] for r in rules_by_hazard[_safe_text(rule.get("hazard_type"))] if r["id"] != rule["id"]]
        zh_phrase, en_phrase = _hazard_phrase(rule)
        scene_list = list(rule.get("scene", ["campus"]))
        for idx, template in enumerate(POSITIVE_TEMPLATES):
            for v in range(2):
                scene = scene_list[(idx + v) % len(scene_list)]
                scene_text = SCENE_TEXT.get(scene, scene)
                query = template.format(
                    scene=scene,
                    scene_text=scene_text,
                    hazard_phrase=zh_phrase,
                    hazard_phrase_en=en_phrase,
                )
                difficulty = "easy"
                if (idx + v) % 3 == 1:
                    query = f"{query} {HARD_DISTRACTORS[(idx + v) % len(HARD_DISTRACTORS)]}"
                    difficulty = "hard"
                elif (idx + v) % 3 == 2:
                    query = f"{query} 请优先返回1-2条最关键依据。"
                    difficulty = "blind"
                if v == 1:
                    query += " 并补充一句可执行整改建议。"

                expected = [rule["id"]]
                if siblings and (idx + v) % 2 == 0:
                    expected.append(siblings[(idx + v) % len(siblings)])

                cases.append(
                    {
                        "name": f"rule_{rule['id']}_{idx}_v{v}",
                        "scene": scene,
                        "query": query,
                        "expected_ids": expected,
                        "difficulty": difficulty,
                        "source": "rule_expansion",
                    }
                )

    # Dataset-driven expansion
    datasets = manifest.get("datasets", []) if isinstance(manifest, dict) else []
    for ds in datasets:
        if not isinstance(ds, dict):
            continue
        ds_id = _safe_text(ds.get("id"), "dataset")
        ds_name = _safe_text(ds.get("name"), ds_id)
        mappings = [_safe_text(x) for x in ds.get("hazard_mapping", []) if _safe_text(x)]

        mapped_rule_ids: List[str] = []
        for signal in mappings:
            mapped_rule_ids.extend(DATASET_SIGNAL_MAPPINGS.get(signal, []))
            if signal in rules_by_hazard:
                mapped_rule_ids.extend([r["id"] for r in rules_by_hazard[signal]])

        mapped_rule_ids = [rid for rid in dict.fromkeys(mapped_rule_ids) if rid in rules_by_id]
        if not mapped_rule_ids:
            continue

        for idx, rid in enumerate(mapped_rule_ids):
            rule = rules_by_id[rid]
            zh_phrase, en_phrase = _hazard_phrase(rule)
            scene_candidates = rule.get("scene", ["campus"])
            for v in range(2):
                scene = scene_candidates[(idx + v) % len(scene_candidates)]
                scene_text = SCENE_TEXT.get(scene, scene)

                base_query = (
                    f"参考公开数据集{ds_name}的场景分布，在{scene_text}发现{zh_phrase}，"
                    "请给出法规依据并说明整改优先级。"
                )
                if (idx + v) % 2 == 1:
                    base_query += f" Also explain in English briefly: {en_phrase}."
                if v == 1:
                    base_query += f" {HARD_DISTRACTORS[(idx + v) % len(HARD_DISTRACTORS)]}"

                cases.append(
                    {
                        "name": f"ds_{ds_id}_{rid}_{idx}_v{v}",
                        "scene": scene,
                        "query": base_query,
                        "expected_ids": [rid],
                        "difficulty": "hard" if (idx + v) % 2 else "easy",
                        "source": f"dataset:{ds_id}",
                    }
                )

    # Dedupe and target truncate
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in cases:
        key = (_safe_text(item.get("scene")), _safe_text(item.get("query")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    if len(deduped) > target_size:
        # Keep all seed cases, then balanced sample from others.
        seed_part = [c for c in deduped if c.get("source") == "seed_benchmark"]
        other_part = [c for c in deduped if c.get("source") != "seed_benchmark"]
        rng.shuffle(other_part)
        keep_n = max(target_size - len(seed_part), 0)
        deduped = seed_part + other_part[:keep_n]

    return deduped


def build_open_set_cases(size: int, seed: int) -> List[Dict[str, Any]]:
    rng = random.Random(seed + 1007)
    scenes = ["campus", "dormitory", "office", "residential", "factory", "industrial", "construction"]
    cases: List[Dict[str, Any]] = []

    for i in range(size):
        scene = scenes[i % len(scenes)]
        scene_text = SCENE_TEXT.get(scene, scene)
        q = OPEN_SET_TEMPLATES[i % len(OPEN_SET_TEMPLATES)].format(scene=scene, scene_text=scene_text)
        if i % 2 == 1:
            q += " 请只在证据充分时给结论，否则请明确说明需人工复核。"
        if i % 3 == 2:
            q += " " + HARD_DISTRACTORS[i % len(HARD_DISTRACTORS)]
        cases.append(
            {
                "name": f"open_set_{i:04d}",
                "scene": scene,
                "query": q,
                "expected_ids": [],
                "expect_refusal": True,
                "difficulty": "open_set",
                "source": "open_set_protocol",
            }
        )

    rng.shuffle(cases)
    return cases


def summarize(cases: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    case_list = list(cases)
    by_scene = Counter(_safe_text(c.get("scene"), "unknown") for c in case_list)
    by_diff = Counter(_safe_text(c.get("difficulty"), "unknown") for c in case_list)
    by_src = Counter(_safe_text(c.get("source"), "unknown") for c in case_list)
    return {
        "count": len(case_list),
        "scene_distribution": dict(sorted(by_scene.items())),
        "difficulty_distribution": dict(sorted(by_diff.items())),
        "source_distribution": dict(sorted(by_src.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a larger benchmark suite for retrieval and guardrail evaluation.")
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE, help="Seed benchmark path.")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES, help="Rule file path.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Public dataset manifest path.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output path for positive benchmark.")
    parser.add_argument("--open-set-out", type=Path, default=DEFAULT_OPEN_SET_OUT, help="Output path for open-set benchmark.")
    parser.add_argument("--target-size", type=int, default=600, help="Target case count for positive benchmark.")
    parser.add_argument("--open-set-size", type=int, default=160, help="Case count for open-set benchmark.")
    parser.add_argument("--seed", type=int, default=20260419, help="Random seed.")
    args = parser.parse_args()

    seed_cases = load_seed_cases(args.base)
    rules = load_rules(args.rules)
    manifest = load_json(args.manifest)

    large_cases = build_large_cases(seed_cases, rules, manifest, target_size=max(args.target_size, len(seed_cases)), seed=args.seed)
    open_set_cases = build_open_set_cases(size=max(args.open_set_size, 20), seed=args.seed)

    args.out.write_text(json.dumps(large_cases, ensure_ascii=False, indent=2), encoding="utf-8")
    args.open_set_out.write_text(json.dumps(open_set_cases, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "positive": summarize(large_cases),
        "open_set": summarize(open_set_cases),
        "paths": {"positive": str(args.out), "open_set": str(args.open_set_out)},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
