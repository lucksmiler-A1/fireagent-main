#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from eval_retrieval import evaluate_profile, load_cases


ROOT = Path(__file__).resolve().parent
DEFAULT_DEV = ROOT / "retrieval_benchmark_v2.json"
DEFAULT_BLIND = ROOT / "retrieval_benchmark_blind_v1.json"
DEFAULT_JSON = ROOT / "experiments_profile_matrix_blind.json"


def build_profile_overrides() -> List[Tuple[str, Dict[str, Any]]]:
    base = {
        "RAG_ENABLE_QUERY_REWRITE": True,
        "RAG_QUERY_REWRITE_USE_LLM": False,
        "RAG_ENABLE_DENSE_RETRIEVAL": False,
        "RAG_ENABLE_RERANK": False,
        "RAG_ENABLE_DYNAMIC_QUERY_BUDGET": True,
        "RAG_ENABLE_MMR_SELECTION": True,
        "RAG_ENABLE_HAZARD_HINT_ROUTING": True,
    }
    iter7 = dict(base)
    iter7.update(
        {
            "RAG_ENABLE_SET_SELECTION": False,
            "RAG_ENABLE_EVIDENCE_TREE_SEARCH": False,
        }
    )
    iter8 = dict(base)
    iter8.update(
        {
            "RAG_ENABLE_SET_SELECTION": True,
            "RAG_ENABLE_EVIDENCE_TREE_SEARCH": False,
        }
    )
    iter9 = dict(base)
    iter9.update(
        {
            "RAG_ENABLE_SET_SELECTION": True,
            "RAG_ENABLE_EVIDENCE_TREE_SEARCH": True,
        }
    )
    return [("iter7_dynamic", iter7), ("iter8_set_selection", iter8), ("iter9_evidence_tree", iter9)]


def slim_report(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "profile": report["profile"],
        "case_count": report["case_count"],
        "top1_hit_rate": report["top1_hit_rate"],
        "top3_hit_rate": report["top3_hit_rate"],
        "mrr": report["mrr"],
        "avg_latency_ms": report.get("avg_latency_ms", 0.0),
        "p95_latency_ms": report.get("p95_latency_ms", 0.0),
    }


def print_table(title: str, rows: List[Dict[str, Any]]) -> None:
    print(f"\n[{title}]")
    for r in rows:
        print(
            f"{r['profile']}: top1={r['top1_hit_rate']:.2%}, top3={r['top3_hit_rate']:.2%}, "
            f"mrr={r['mrr']:.4f}, avg_ms={r['avg_latency_ms']:.2f}, p95_ms={r['p95_latency_ms']:.2f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate iter7/iter8/iter9 profile matrix on dev + blind sets.")
    parser.add_argument("--dev", type=Path, default=DEFAULT_DEV)
    parser.add_argument("--blind", type=Path, default=DEFAULT_BLIND)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()

    dev_cases = load_cases(args.dev)
    blind_cases = load_cases(args.blind)

    all_reports: Dict[str, List[Dict[str, Any]]] = {"dev": [], "blind": []}
    for profile_name, overrides in build_profile_overrides():
        dev_report = evaluate_profile(profile_name, dev_cases, overrides, top_k=max(args.top_k, 3))
        blind_report = evaluate_profile(profile_name, blind_cases, overrides, top_k=max(args.top_k, 3))
        all_reports["dev"].append(slim_report(dev_report))
        all_reports["blind"].append(slim_report(blind_report))

    print_table("dev", all_reports["dev"])
    print_table("blind", all_reports["blind"])

    args.json.write_text(json.dumps(all_reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved JSON report to: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

