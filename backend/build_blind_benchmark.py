#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "retrieval_benchmark_v2.json"
DEFAULT_OUTPUT = ROOT / "retrieval_benchmark_blind_v1.json"


REPLACE_RULES: List[tuple[str, str]] = [
    ("消防", "火灾安全"),
    ("隐患", "风险点"),
    ("依据是什么", "对应规范是什么"),
    ("是否合规", "是否满足要求"),
    ("行不行", "是否允许"),
    ("楼道", "疏散通道"),
    ("充电", "补能"),
    ("电动车", "两轮电动车"),
    ("配电箱", "配电柜"),
    ("插线板", "接线板"),
    ("灭火器", "手提灭火器"),
    ("消火栓", "室内消火栓"),
    ("报警", "火灾报警"),
    ("喷淋", "自动喷水"),
    ("电线", "线路"),
]

PREFIX_POOL = [
    "请按巡检视角判断：",
    "作为安全审查，请给出结论：",
    "从合规角度快速核对：",
]

SUFFIX_POOL = [
    "并指出优先整改项。",
    "请附上可执行建议。",
    "请按规范要点回答。",
]


def stable_pick(text: str, n: int) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % max(n, 1)


def rewrite_query(query: str, name: str) -> str:
    text = str(query)
    for old, new in REPLACE_RULES:
        text = text.replace(old, new)
    pref = PREFIX_POOL[stable_pick(name + "::pref", len(PREFIX_POOL))]
    suff = SUFFIX_POOL[stable_pick(name + "::suf", len(SUFFIX_POOL))]
    return f"{pref}{text}；{suff}"


def build_blind_cases(cases: List[Dict[str, object]]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for item in cases:
        name = str(item.get("name") or "case")
        out.append(
            {
                "name": f"{name}__blind",
                "scene": item.get("scene", "campus"),
                "query": rewrite_query(str(item.get("query") or ""), name),
                "expected_ids": item.get("expected_ids", []),
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a blind benchmark with paraphrased queries.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Input benchmark must be a JSON list.")
    blind = build_blind_cases(data)
    args.output.write_text(json.dumps(blind, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"input_cases={len(data)} output_cases={len(blind)}")
    print(f"saved={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

