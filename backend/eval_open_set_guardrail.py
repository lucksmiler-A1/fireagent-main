#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.retriever import rule_retriever

DEFAULT_BENCHMARK = ROOT / "retrieval_benchmark_open_set_v1.json"
DEFAULT_JSON = ROOT / "experiments_open_set_guardrail_v1.json"


def load_cases(path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError("open-set benchmark must be a JSON list")
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        scene = str(item.get("scene") or "campus").strip() or "campus"
        if not query:
            continue
        out.append(
            {
                "name": str(item.get("name") or f"case_{len(out)}").strip(),
                "scene": scene,
                "query": query,
                "expect_refusal": bool(item.get("expect_refusal", True)),
            }
        )
    if not out:
        raise ValueError("no valid open-set cases")
    return out


@contextmanager
def temporary_settings(overrides: Dict[str, Any]):
    old_values: Dict[str, Any] = {}
    for key, value in overrides.items():
        old_values[key] = getattr(settings, key)
        setattr(settings, key, value)
    try:
        yield
    finally:
        for key, value in old_values.items():
            setattr(settings, key, value)


def evaluate(cases: List[Dict[str, Any]], top_k: int, overrides: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    latency: List[float] = []

    with temporary_settings(overrides):
        for case in cases:
            begin = perf_counter()
            result = rule_retriever.retrieve_with_debug(case["query"], case["scene"], top_k=top_k)
            elapsed = (perf_counter() - begin) * 1000.0
            latency.append(elapsed)

            rules = result.get("rules", []) if isinstance(result, dict) else []
            returned_ids = [str(x.get("id", "")) for x in rules if isinstance(x, dict)]
            predicted_refusal = len(returned_ids) == 0
            correct = predicted_refusal == case["expect_refusal"]

            rows.append(
                {
                    "name": case["name"],
                    "scene": case["scene"],
                    "query": case["query"],
                    "expect_refusal": case["expect_refusal"],
                    "predicted_refusal": predicted_refusal,
                    "returned_ids": returned_ids,
                    "correct": correct,
                    "latency_ms": round(elapsed, 2),
                }
            )

    correct_count = sum(1 for r in rows if r["correct"])
    refusal_precision = (
        sum(1 for r in rows if r["predicted_refusal"] and r["expect_refusal"]) /
        max(sum(1 for r in rows if r["predicted_refusal"]), 1)
    )
    refusal_recall = (
        sum(1 for r in rows if r["predicted_refusal"] and r["expect_refusal"]) /
        max(sum(1 for r in rows if r["expect_refusal"]), 1)
    )

    sorted_latency = sorted(latency)
    p95_idx = int(round(0.95 * (len(sorted_latency) - 1))) if sorted_latency else 0
    return {
        "case_count": len(rows),
        "accuracy": round(correct_count / max(len(rows), 1), 4),
        "refusal_precision": round(refusal_precision, 4),
        "refusal_recall": round(refusal_recall, 4),
        "avg_latency_ms": round(mean(latency), 2) if latency else 0.0,
        "p95_latency_ms": round(sorted_latency[p95_idx], 2) if sorted_latency else 0.0,
        "false_accept_count": sum(1 for r in rows if (not r["predicted_refusal"]) and r["expect_refusal"]),
        "rows": rows,
    }


def build_profiles() -> List[Dict[str, Any]]:
    return [
        {
            "name": "hybrid_local_guardrail",
            "overrides": {
                "RAG_ENABLE_QUERY_REWRITE": True,
                "RAG_QUERY_REWRITE_USE_LLM": False,
                "RAG_ENABLE_DYNAMIC_QUERY_BUDGET": True,
                "RAG_ENABLE_MMR_SELECTION": True,
                "RAG_ENABLE_SET_SELECTION": True,
                "RAG_ENABLE_EVIDENCE_TREE_SEARCH": False,
                "RAG_ENABLE_HAZARD_HINT_ROUTING": True,
                "RAG_ENABLE_DENSE_RETRIEVAL": False,
                "RAG_ENABLE_RERANK": False,
                "RAG_RETRIEVAL_MODE": "hybrid",
            },
        },
        {
            "name": "strict_guardrail_keyword",
            "overrides": {
                "RAG_ENABLE_QUERY_REWRITE": False,
                "RAG_QUERY_REWRITE_USE_LLM": False,
                "RAG_ENABLE_DYNAMIC_QUERY_BUDGET": False,
                "RAG_ENABLE_MMR_SELECTION": False,
                "RAG_ENABLE_SET_SELECTION": False,
                "RAG_ENABLE_EVIDENCE_TREE_SEARCH": False,
                "RAG_ENABLE_HAZARD_HINT_ROUTING": False,
                "RAG_ENABLE_DENSE_RETRIEVAL": False,
                "RAG_ENABLE_RERANK": False,
                "RAG_RETRIEVAL_MODE": "keyword",
            },
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate open-set guardrail behavior of retriever stage.")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--max-cases", type=int, default=0, help="Optional cap for quick test.")
    args = parser.parse_args()

    cases = load_cases(args.benchmark)
    if args.max_cases > 0:
        cases = cases[: args.max_cases]

    reports: List[Dict[str, Any]] = []
    for profile in build_profiles():
        report = evaluate(cases, top_k=max(args.top_k, 1), overrides=profile["overrides"])
        report["profile"] = profile["name"]
        reports.append(report)
        print(f"[{profile['name']}]")
        print(f"cases={report['case_count']}")
        print(f"accuracy={report['accuracy']:.2%}")
        print(f"refusal_precision={report['refusal_precision']:.2%}")
        print(f"refusal_recall={report['refusal_recall']:.2%}")
        print(f"avg_latency_ms={report['avg_latency_ms']:.2f}")
        print(f"p95_latency_ms={report['p95_latency_ms']:.2f}")
        print(f"false_accept_count={report['false_accept_count']}")
        print("")

    args.json.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved={args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
