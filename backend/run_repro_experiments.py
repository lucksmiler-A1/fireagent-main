#!/usr/bin/env python3
"""Run reproducible local experiments for FireAgent.

This script intentionally avoids external model calls by default. It evaluates
the retrieval and open-set guardrail stages with local benchmark JSON files.
External direct-model baselines can be added separately, but must be reported as
"not run" unless a valid API key and image/text benchmark are available.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Dict, Iterable, List, Sequence

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.guardrail import filter_with_guardrail
from app.services.retriever import rule_retriever


DEFAULT_RETRIEVAL_BENCHMARK = ROOT / "retrieval_benchmark_large_v1.json"
DEFAULT_OPEN_SET_BENCHMARK = ROOT / "retrieval_benchmark_open_set_v1.json"
DEFAULT_JSON = REPO_ROOT / "results" / "repro_experiments.json"
DEFAULT_MD = REPO_ROOT / "results" / "summary_tables.md"


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


def load_retrieval_cases(path: Path, max_cases: int = 0) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError(f"{path} must be a JSON list")
    cases: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        expected_ids = [str(x).strip() for x in item.get("expected_ids", []) if str(x).strip()]
        if not query or not expected_ids:
            continue
        cases.append(
            {
                "name": str(item.get("name") or f"case_{len(cases):04d}"),
                "scene": str(item.get("scene") or "campus").strip() or "campus",
                "query": query,
                "expected_ids": expected_ids,
                "difficulty": str(item.get("difficulty") or ""),
                "source": str(item.get("source") or ""),
            }
        )
        if max_cases > 0 and len(cases) >= max_cases:
            break
    if not cases:
        raise ValueError(f"no valid retrieval cases in {path}")
    return cases


def load_open_set_cases(path: Path, max_cases: int = 0) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError(f"{path} must be a JSON list")
    cases: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        if not query:
            continue
        cases.append(
            {
                "name": str(item.get("name") or f"open_{len(cases):04d}"),
                "scene": str(item.get("scene") or "campus").strip() or "campus",
                "query": query,
                "expect_refusal": bool(item.get("expect_refusal", True)),
                "difficulty": str(item.get("difficulty") or ""),
                "source": str(item.get("source") or ""),
            }
        )
        if max_cases > 0 and len(cases) >= max_cases:
            break
    if not cases:
        raise ValueError(f"no valid open-set cases in {path}")
    return cases


def reciprocal_rank(found_ids: Sequence[str], expected_ids: Sequence[str]) -> float:
    expected = set(expected_ids)
    for idx, rule_id in enumerate(found_ids, start=1):
        if rule_id in expected:
            return 1.0 / idx
    return 0.0


def percentile(values: Sequence[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * p))
    return float(ordered[max(0, min(idx, len(ordered) - 1))])


def summarize_retrieval(profile: str, rows: List[Dict[str, Any]], latency_ms: List[float]) -> Dict[str, Any]:
    n = max(len(rows), 1)
    return {
        "profile": profile,
        "case_count": len(rows),
        "top1_hit_rate": round(sum(1 for r in rows if r["hit_top1"]) / n, 4),
        "top3_hit_rate": round(sum(1 for r in rows if r["hit_top3"]) / n, 4),
        "mrr": round(mean(float(r["mrr"]) for r in rows), 4) if rows else 0.0,
        "avg_latency_ms": round(mean(latency_ms), 2) if latency_ms else 0.0,
        "p95_latency_ms": round(percentile(latency_ms, 0.95), 2),
        "rows": rows,
    }


def evaluate_no_rag(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for case in cases:
        rows.append(
            {
                "name": case["name"],
                "scene": case["scene"],
                "query": case["query"],
                "expected_ids": case["expected_ids"],
                "returned_ids": [],
                "hit_top1": False,
                "hit_top3": False,
                "mrr": 0.0,
                "latency_ms": 0.0,
            }
        )
    return summarize_retrieval("B0_no_rag_no_rule_evidence", rows, [0.0 for _ in rows])


def evaluate_retrieval_profile(
    name: str,
    cases: List[Dict[str, Any]],
    overrides: Dict[str, Any],
    top_k: int,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    latency: List[float] = []
    with temporary_settings(overrides):
        for case in cases:
            started = perf_counter()
            result = rule_retriever.retrieve_with_debug(case["query"], case["scene"], top_k=max(3, top_k))
            elapsed = (perf_counter() - started) * 1000.0
            latency.append(elapsed)
            returned_ids = [str(item.get("id", "")) for item in result.get("rules", []) if isinstance(item, dict)]
            expected = set(case["expected_ids"])
            rows.append(
                {
                    "name": case["name"],
                    "scene": case["scene"],
                    "query": case["query"],
                    "expected_ids": case["expected_ids"],
                    "returned_ids": returned_ids,
                    "hit_top1": bool(returned_ids[:1] and returned_ids[0] in expected),
                    "hit_top3": any(rule_id in expected for rule_id in returned_ids[:3]),
                    "mrr": reciprocal_rank(returned_ids[:top_k], case["expected_ids"]),
                    "latency_ms": round(elapsed, 2),
                }
            )
    report = summarize_retrieval(name, rows, latency)
    report["overrides"] = overrides
    return report


def evaluate_open_set_profile(
    name: str,
    cases: List[Dict[str, Any]],
    overrides: Dict[str, Any],
    *,
    top_k: int,
    use_guardrail_wrapper: bool,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    latency: List[float] = []
    with temporary_settings(overrides):
        for case in cases:
            started = perf_counter()
            result = rule_retriever.retrieve_with_debug(case["query"], case["scene"], top_k=max(1, top_k))
            rules = [x for x in result.get("rules", []) if isinstance(x, dict)]
            guardrail_decision = None
            if use_guardrail_wrapper:
                rules, guardrail_decision = filter_with_guardrail(
                    query=case["query"],
                    scene=case["scene"],
                    retrieved_rules=rules,
                    debug=result.get("debug", {}),
                )
            elapsed = (perf_counter() - started) * 1000.0
            latency.append(elapsed)
            returned_ids = [str(item.get("id", "")) for item in rules]
            predicted_refusal = len(returned_ids) == 0
            rows.append(
                {
                    "name": case["name"],
                    "scene": case["scene"],
                    "query": case["query"],
                    "expect_refusal": case["expect_refusal"],
                    "predicted_refusal": predicted_refusal,
                    "returned_ids": returned_ids,
                    "correct": predicted_refusal == case["expect_refusal"],
                    "latency_ms": round(elapsed, 2),
                    "guardrail": guardrail_decision.to_dict() if guardrail_decision else None,
                }
            )

    tp_refusal = sum(1 for r in rows if r["predicted_refusal"] and r["expect_refusal"])
    predicted_refusal_count = sum(1 for r in rows if r["predicted_refusal"])
    expected_refusal_count = sum(1 for r in rows if r["expect_refusal"])
    correct = sum(1 for r in rows if r["correct"])
    return {
        "profile": name,
        "case_count": len(rows),
        "accuracy": round(correct / max(len(rows), 1), 4),
        "refusal_precision": round(tp_refusal / max(predicted_refusal_count, 1), 4),
        "refusal_recall": round(tp_refusal / max(expected_refusal_count, 1), 4),
        "false_accept_count": sum(1 for r in rows if (not r["predicted_refusal"]) and r["expect_refusal"]),
        "avg_latency_ms": round(mean(latency), 2) if latency else 0.0,
        "p95_latency_ms": round(percentile(latency, 0.95), 2),
        "overrides": overrides,
        "use_guardrail_wrapper": use_guardrail_wrapper,
        "rows": rows,
    }


def baseline_profiles() -> List[tuple[str, Dict[str, Any]]]:
    return [
        (
            "B1_standard_single_keyword_rag",
            {
                "RAG_ENABLE_QUERY_REWRITE": False,
                "RAG_QUERY_REWRITE_USE_LLM": False,
                "RAG_ENABLE_TEXT_REPAIR": True,
                "RAG_ENABLE_DYNAMIC_TOP_K": False,
                "RAG_ENABLE_DYNAMIC_QUERY_BUDGET": False,
                "RAG_ENABLE_MMR_SELECTION": False,
                "RAG_ENABLE_SET_SELECTION": False,
                "RAG_ENABLE_EVIDENCE_TREE_SEARCH": False,
                "RAG_ENABLE_HAZARD_HINT_ROUTING": False,
                "RAG_ENABLE_DENSE_RETRIEVAL": False,
                "RAG_ENABLE_RERANK": False,
                "RAG_RETRIEVAL_MODE": "keyword",
            },
        ),
        (
            "B2_standard_single_hybrid_rag",
            {
                "RAG_ENABLE_QUERY_REWRITE": False,
                "RAG_QUERY_REWRITE_USE_LLM": False,
                "RAG_ENABLE_TEXT_REPAIR": True,
                "RAG_ENABLE_DYNAMIC_TOP_K": False,
                "RAG_ENABLE_DYNAMIC_QUERY_BUDGET": False,
                "RAG_ENABLE_MMR_SELECTION": False,
                "RAG_ENABLE_SET_SELECTION": False,
                "RAG_ENABLE_EVIDENCE_TREE_SEARCH": False,
                "RAG_ENABLE_HAZARD_HINT_ROUTING": False,
                "RAG_ENABLE_DENSE_RETRIEVAL": False,
                "RAG_ENABLE_RERANK": False,
                "RAG_RETRIEVAL_MODE": "hybrid",
            },
        ),
        (
            "Ours_full_local_no_external_embedding",
            full_local_profile(),
        ),
    ]


def full_local_profile() -> Dict[str, Any]:
    return {
        "RAG_ENABLE_QUERY_REWRITE": True,
        "RAG_QUERY_REWRITE_USE_LLM": False,
        "RAG_ENABLE_TEXT_REPAIR": True,
        "RAG_ENABLE_DYNAMIC_TOP_K": True,
        "RAG_ENABLE_DYNAMIC_QUERY_BUDGET": True,
        "RAG_ENABLE_MMR_SELECTION": True,
        "RAG_ENABLE_SET_SELECTION": True,
        "RAG_ENABLE_EVIDENCE_TREE_SEARCH": True,
        "RAG_ENABLE_HAZARD_HINT_ROUTING": True,
        "RAG_ENABLE_DENSE_RETRIEVAL": False,
        "RAG_ENABLE_RERANK": False,
        "RAG_RETRIEVAL_MODE": "hybrid",
    }


def ablation_profiles() -> List[tuple[str, Dict[str, Any]]]:
    full = full_local_profile()

    def wo(**changes: Any) -> Dict[str, Any]:
        profile = dict(full)
        profile.update(changes)
        return profile

    return [
        ("full", full),
        ("wo_query_rewrite", wo(RAG_ENABLE_QUERY_REWRITE=False)),
        ("wo_dynamic_query_budget", wo(RAG_ENABLE_DYNAMIC_QUERY_BUDGET=False, RAG_ENABLE_DYNAMIC_TOP_K=False)),
        ("wo_set_selection", wo(RAG_ENABLE_SET_SELECTION=False)),
        ("wo_evidence_tree", wo(RAG_ENABLE_EVIDENCE_TREE_SEARCH=False)),
        ("wo_hazard_hint_router", wo(RAG_ENABLE_HAZARD_HINT_ROUTING=False)),
        (
            "keyword_only",
            wo(
                RAG_RETRIEVAL_MODE="keyword",
                RAG_ENABLE_MMR_SELECTION=False,
                RAG_ENABLE_SET_SELECTION=False,
                RAG_ENABLE_EVIDENCE_TREE_SEARCH=False,
                RAG_ENABLE_HAZARD_HINT_ROUTING=False,
            ),
        ),
    ]


def write_markdown(report: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    meta = report["metadata"]
    lines.append("# Reproducible Experiment Summary")
    lines.append("")
    lines.append("All numeric results in this file were generated by `backend/run_repro_experiments.py` in the current workspace.")
    lines.append("")
    lines.append("## Run Metadata")
    lines.append("")
    lines.append(f"- Timestamp: `{meta['timestamp']}`")
    lines.append(f"- Python: `{meta['python']}`")
    lines.append(f"- Platform: `{meta['platform']}`")
    lines.append(f"- Retrieval benchmark: `{meta['retrieval_benchmark']}`")
    lines.append(f"- Open-set benchmark: `{meta['open_set_benchmark']}`")
    lines.append(f"- Retrieval cases: `{meta['retrieval_case_count']}`")
    lines.append(f"- Open-set cases: `{meta['open_set_case_count']}`")
    lines.append(f"- Retrieval case cap argument: `{meta['max_cases_arg']}`")
    lines.append(f"- Open-set case cap argument: `{meta['max_open_set_cases_arg']}`")
    lines.append(f"- External model calls: `not used`")
    lines.append("")

    lines.append("## Baseline Comparison")
    lines.append("")
    lines.append("| Profile | Cases | Top1 | Top3 | MRR | Avg Latency ms | P95 Latency ms |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for row in report["baselines"]:
        lines.append(
            f"| {row['profile']} | {row['case_count']} | {row['top1_hit_rate']:.4f} | "
            f"{row['top3_hit_rate']:.4f} | {row['mrr']:.4f} | {row['avg_latency_ms']:.2f} | {row['p95_latency_ms']:.2f} |"
        )
    lines.append("")

    lines.append("## Ablation Study")
    lines.append("")
    lines.append("| Profile | Cases | Top1 | Top3 | MRR | Avg Latency ms | P95 Latency ms |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for row in report["ablations"]:
        lines.append(
            f"| {row['profile']} | {row['case_count']} | {row['top1_hit_rate']:.4f} | "
            f"{row['top3_hit_rate']:.4f} | {row['mrr']:.4f} | {row['avg_latency_ms']:.2f} | {row['p95_latency_ms']:.2f} |"
        )
    lines.append("")

    lines.append("## Open-Set Guardrail")
    lines.append("")
    lines.append("| Profile | Cases | Accuracy | Refusal Precision | Refusal Recall | False Accept | Avg Latency ms |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for row in report["open_set"]:
        lines.append(
            f"| {row['profile']} | {row['case_count']} | {row['accuracy']:.4f} | "
            f"{row['refusal_precision']:.4f} | {row['refusal_recall']:.4f} | "
            f"{row['false_accept_count']} | {row['avg_latency_ms']:.2f} |"
        )
    lines.append("")

    lines.append("## Explicit Non-Results")
    lines.append("")
    for item in report["non_results"]:
        lines.append(f"- **{item['name']}**: {item['reason']}")
    lines.append("")
    lines.append("## Re-run Command")
    lines.append("")
    lines.append("```powershell")
    lines.append("# Run from the repository root")
    command = "python backend\\run_repro_experiments.py --json results\\repro_experiments.json --markdown results\\summary_tables.md"
    if int(meta.get("max_cases_arg", 0)):
        command += f" --max-cases {int(meta['max_cases_arg'])}"
    if int(meta.get("max_open_set_cases_arg", 0)):
        command += f" --max-open-set-cases {int(meta['max_open_set_cases_arg'])}"
    lines.append(command)
    lines.append("```")
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> Dict[str, Any]:
    retrieval_cases = load_retrieval_cases(args.retrieval_benchmark, max_cases=args.max_cases)
    open_set_cases = load_open_set_cases(args.open_set_benchmark, max_cases=args.max_open_set_cases)

    baselines = [evaluate_no_rag(retrieval_cases)]
    for name, overrides in baseline_profiles():
        baselines.append(evaluate_retrieval_profile(name, retrieval_cases, overrides, top_k=args.top_k))

    ablations = [
        evaluate_retrieval_profile(name, retrieval_cases, overrides, top_k=args.top_k)
        for name, overrides in ablation_profiles()
    ]

    open_set_profiles = [
        (
            "empty_result_guardrail_full_local",
            full_local_profile(),
            False,
        ),
        (
            "guardrail_wrapper_full_local",
            full_local_profile(),
            True,
        ),
        (
            "strict_keyword_empty_result",
            {
                "RAG_ENABLE_QUERY_REWRITE": False,
                "RAG_QUERY_REWRITE_USE_LLM": False,
                "RAG_ENABLE_TEXT_REPAIR": True,
                "RAG_ENABLE_DYNAMIC_TOP_K": False,
                "RAG_ENABLE_DYNAMIC_QUERY_BUDGET": False,
                "RAG_ENABLE_MMR_SELECTION": False,
                "RAG_ENABLE_SET_SELECTION": False,
                "RAG_ENABLE_EVIDENCE_TREE_SEARCH": False,
                "RAG_ENABLE_HAZARD_HINT_ROUTING": False,
                "RAG_ENABLE_DENSE_RETRIEVAL": False,
                "RAG_ENABLE_RERANK": False,
                "RAG_RETRIEVAL_MODE": "keyword",
            },
            False,
        ),
    ]
    open_set = [
        evaluate_open_set_profile(name, open_set_cases, overrides, top_k=args.top_k, use_guardrail_wrapper=wrapped)
        for name, overrides, wrapped in open_set_profiles
    ]

    return {
        "metadata": {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "python": sys.version.replace("\n", " "),
            "platform": platform.platform(),
            "retrieval_benchmark": str(args.retrieval_benchmark.resolve()),
            "open_set_benchmark": str(args.open_set_benchmark.resolve()),
            "retrieval_case_count": len(retrieval_cases),
            "open_set_case_count": len(open_set_cases),
            "max_cases_arg": int(args.max_cases),
            "max_open_set_cases_arg": int(args.max_open_set_cases),
        },
        "baselines": baselines,
        "ablations": ablations,
        "open_set": open_set,
        "non_results": [
            {
                "name": "pure_VLM_image_baseline",
                "reason": "Not run: repository does not contain an independent labeled image benchmark with ground-truth hazards, and no external VLM call is made by this local reproducibility script.",
            },
            {
                "name": "direct_external_LLM_no_RAG_baseline",
                "reason": "Not run by default: requires a valid external OpenAI-compatible API key and would introduce non-deterministic provider/network dependence.",
            },
            {
                "name": "mAP_object_detection_baseline",
                "reason": "Not run: repository does not contain bounding-box annotations or a detector checkpoint; current experiments evaluate retrieval/rule-hit quality, not object detection mAP.",
            },
        ],
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local reproducible baselines and ablations.")
    parser.add_argument("--retrieval-benchmark", type=Path, default=DEFAULT_RETRIEVAL_BENCHMARK)
    parser.add_argument("--open-set-benchmark", type=Path, default=DEFAULT_OPEN_SET_BENCHMARK)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--max-open-set-cases", type=int, default=0)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = run(args)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, args.markdown)

    print(f"saved_json={args.json}")
    print(f"saved_markdown={args.markdown}")
    for row in report["baselines"]:
        print(f"baseline {row['profile']}: top1={row['top1_hit_rate']:.4f} top3={row['top3_hit_rate']:.4f} mrr={row['mrr']:.4f}")
    for row in report["open_set"]:
        print(f"open_set {row['profile']}: precision={row['refusal_precision']:.4f} recall={row['refusal_recall']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
