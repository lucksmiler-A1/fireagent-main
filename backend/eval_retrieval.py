#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from statistics import mean
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.retriever import rule_retriever


DEFAULT_BENCHMARK = ROOT / "retrieval_benchmark.json"


def load_cases(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Benchmark file must be a JSON list.")
    cases: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        scene = str(item.get("scene") or "campus").strip() or "campus"
        expected_ids = [str(x).strip() for x in (item.get("expected_ids") or []) if str(x).strip()]
        if not query or not expected_ids:
            continue
        cases.append(
            {
                "name": str(item.get("name") or query[:40]).strip(),
                "query": query,
                "scene": scene,
                "expected_ids": expected_ids,
            }
        )
    if not cases:
        raise ValueError("No valid benchmark cases found.")
    return cases


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


def reciprocal_rank(found_ids: List[str], expected_ids: List[str]) -> float:
    expected = set(expected_ids)
    for idx, rule_id in enumerate(found_ids, start=1):
        if rule_id in expected:
            return 1.0 / idx
    return 0.0


def evaluate_profile(name: str, cases: List[Dict[str, Any]], overrides: Dict[str, Any], top_k: int) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    latency_ms_values: List[float] = []
    with temporary_settings(overrides):
        for case in cases:
            begin = perf_counter()
            result = rule_retriever.retrieve_with_debug(case["query"], case["scene"], top_k=top_k)
            elapsed_ms = (perf_counter() - begin) * 1000.0
            latency_ms_values.append(elapsed_ms)
            returned_ids = [str(item.get("id", "")) for item in result.get("rules", [])]
            expected = set(case["expected_ids"])
            hit_top1 = bool(returned_ids[:1] and returned_ids[0] in expected)
            hit_top3 = any(rule_id in expected for rule_id in returned_ids[: min(3, len(returned_ids))])
            rr = reciprocal_rank(returned_ids[:top_k], case["expected_ids"])

            rows.append(
                {
                    "name": case["name"],
                    "query": case["query"],
                    "scene": case["scene"],
                    "expected_ids": case["expected_ids"],
                    "returned_ids": returned_ids,
                    "hit_top1": hit_top1,
                    "hit_top3": hit_top3,
                    "mrr": rr,
                    "latency_ms": round(elapsed_ms, 2),
                    "debug": result.get("debug", {}),
                }
            )

    top1 = sum(1 for row in rows if row["hit_top1"])
    top3 = sum(1 for row in rows if row["hit_top3"])
    sorted_latency = sorted(latency_ms_values)
    p95_idx = int(round(0.95 * (len(sorted_latency) - 1))) if sorted_latency else 0
    p95_latency = sorted_latency[p95_idx] if sorted_latency else 0.0
    return {
        "profile": name,
        "case_count": len(rows),
        "top1_hits": top1,
        "top3_hits": top3,
        "top1_hit_rate": round(top1 / len(rows), 4),
        "top3_hit_rate": round(top3 / len(rows), 4),
        "mrr": round(mean(row["mrr"] for row in rows), 4),
        "avg_latency_ms": round(mean(latency_ms_values), 2) if latency_ms_values else 0.0,
        "p95_latency_ms": round(p95_latency, 2),
        "rows": rows,
    }


def build_profiles(enable_query_rewrite: bool) -> List[tuple[str, Dict[str, Any]]]:
    profiles = [
        (
            "hybrid",
            {
                "RAG_ENABLE_QUERY_REWRITE": enable_query_rewrite,
                "RAG_QUERY_REWRITE_USE_LLM": False,
                "RAG_ENABLE_DENSE_RETRIEVAL": False,
                "RAG_ENABLE_RERANK": False,
            },
        ),
        (
            "hybrid+dense+rerank",
            {
                "RAG_ENABLE_QUERY_REWRITE": enable_query_rewrite,
                "RAG_QUERY_REWRITE_USE_LLM": False,
                "RAG_ENABLE_DENSE_RETRIEVAL": True,
                "RAG_ENABLE_RERANK": True,
            },
        ),
    ]

    if not (settings.SILICONFLOW_API_KEY or os.getenv("SILICONFLOW_API_KEY")):
        return profiles[:1]
    return profiles


def print_summary(report: Dict[str, Any]) -> None:
    print(f"\n[{report['profile']}]")
    print(f"cases: {report['case_count']}")
    print(f"top1_hit_rate: {report['top1_hit_rate']:.2%}")
    print(f"top3_hit_rate: {report['top3_hit_rate']:.2%}")
    print(f"mrr: {report['mrr']:.4f}")
    print(f"avg_latency_ms: {report.get('avg_latency_ms', 0.0):.2f}")
    print(f"p95_latency_ms: {report.get('p95_latency_ms', 0.0):.2f}")
    print("details:")
    for row in report["rows"]:
        status = "OK" if row["hit_top3"] else "MISS"
        print(f"- {status} {row['name']}: expected={row['expected_ids']} returned={row['returned_ids'][:3]}")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate retrieval hit rate for hybrid vs hybrid+dense+rerank.")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK, help="Path to benchmark JSON file.")
    parser.add_argument("--top-k", type=int, default=5, help="Top-k to retrieve for each query.")
    parser.add_argument("--enable-query-rewrite", action="store_true", help="Enable query rewrite in both profiles.")
    parser.add_argument("--json", type=Path, help="Optional output path for JSON report.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    cases = load_cases(args.benchmark)
    reports = []
    for profile_name, overrides in build_profiles(args.enable_query_rewrite):
        report = evaluate_profile(profile_name, cases, overrides, top_k=max(args.top_k, 3))
        reports.append(report)
        print_summary(report)

    if args.json:
        args.json.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved JSON report to: {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
