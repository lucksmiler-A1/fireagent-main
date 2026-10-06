#!/usr/bin/env python3
"""Strong baseline evaluation for paper.

Implements three required baselines:
  1. naive_topk     - keyword-only top-K, no rewrite, no MMR, no set-selection,
                       no evidence-tree, no hazard-hint, no rerank, no dense.
  2. naive_dense    - dense-only similarity (BAAI/bge-m3) top-K, no other tricks.
  3. naive_hybrid   - keyword + dense linear blend, top-K, no other tricks.
  4. full_system    - the full configured FireAgent retrieval pipeline.

Each baseline reports Top1, Top3, MRR, average latency, P95 latency.
Bootstrap 95% CIs (1000 resamples) are reported per metric.

Usage:
  python eval_publication_strong_baselines.py \
      --benchmark retrieval_benchmark_large_v1.json \
      --json experiments_publication_strong_baselines.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from contextlib import contextmanager
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.retriever import rule_retriever


DEFAULT_BENCHMARK = ROOT / "retrieval_benchmark_large_v1.json"
DEFAULT_JSON = ROOT / "experiments_publication_strong_baselines.json"


def load_cases(path: Path, max_cases: int = 0) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("Benchmark must be a JSON list.")
    cases: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        q = str(item.get("query") or "").strip()
        scene = str(item.get("scene") or "campus").strip() or "campus"
        expected = [str(x).strip() for x in (item.get("expected_ids") or []) if str(x).strip()]
        if not q or not expected:
            continue
        cases.append({
            "name": str(item.get("name") or f"case_{len(cases)}"),
            "query": q,
            "scene": scene,
            "expected_ids": expected,
        })
        if max_cases > 0 and len(cases) >= max_cases:
            break
    if not cases:
        raise ValueError("No valid cases found.")
    return cases


@contextmanager
def temporary_settings(overrides: Dict[str, Any]):
    old: Dict[str, Any] = {}
    for k, v in overrides.items():
        old[k] = getattr(settings, k)
        setattr(settings, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(settings, k, v)


def bootstrap_ci(values: Sequence[float], iterations: int = 1000, seed: int = 20260427) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "lo": 0.0, "hi": 0.0}
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(iterations):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return {
        "mean": sum(values) / n,
        "lo": means[int(0.025 * iterations)],
        "hi": means[int(0.975 * iterations)],
    }


def reciprocal_rank(found: Sequence[str], expected: Sequence[str]) -> float:
    expected_set = set(expected)
    for i, rid in enumerate(found, start=1):
        if rid in expected_set:
            return 1.0 / i
    return 0.0


def hit_at_k(found: Sequence[str], expected: Sequence[str], k: int) -> bool:
    expected_set = set(expected)
    for rid in found[:k]:
        if rid in expected_set:
            return True
    return False


def percentile(values: Sequence[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(p / 100.0 * (len(s) - 1))
    return s[idx]


# Configuration profiles
PROFILES: Dict[str, Dict[str, Any]] = {
    "naive_topk_keyword_only": {
        "RAG_RETRIEVAL_MODE": "keyword",
        "RAG_ENABLE_QUERY_REWRITE": False,
        "RAG_QUERY_REWRITE_USE_LLM": False,
        "RAG_ENABLE_DENSE_RETRIEVAL": False,
        "RAG_ENABLE_RERANK": False,
        "RAG_ENABLE_DYNAMIC_TOP_K": False,
        "RAG_ENABLE_DYNAMIC_QUERY_BUDGET": False,
        "RAG_ENABLE_MMR_SELECTION": False,
        "RAG_ENABLE_SET_SELECTION": False,
        "RAG_ENABLE_EVIDENCE_TREE_SEARCH": False,
        "RAG_ENABLE_HAZARD_HINT_ROUTING": False,
        "RAG_ENABLE_TEXT_REPAIR": False,
        "RAG_TOP_K": 3,
    },
    "naive_dense_only": {
        "RAG_RETRIEVAL_MODE": "vector",
        "RAG_ENABLE_QUERY_REWRITE": False,
        "RAG_QUERY_REWRITE_USE_LLM": False,
        "RAG_ENABLE_DENSE_RETRIEVAL": True,
        "RAG_ENABLE_RERANK": False,
        "RAG_ENABLE_DYNAMIC_TOP_K": False,
        "RAG_ENABLE_DYNAMIC_QUERY_BUDGET": False,
        "RAG_ENABLE_MMR_SELECTION": False,
        "RAG_ENABLE_SET_SELECTION": False,
        "RAG_ENABLE_EVIDENCE_TREE_SEARCH": False,
        "RAG_ENABLE_HAZARD_HINT_ROUTING": False,
        "RAG_ENABLE_TEXT_REPAIR": False,
        "RAG_TOP_K": 3,
    },
    "naive_hybrid": {
        "RAG_RETRIEVAL_MODE": "hybrid",
        "RAG_ENABLE_QUERY_REWRITE": False,
        "RAG_QUERY_REWRITE_USE_LLM": False,
        "RAG_ENABLE_DENSE_RETRIEVAL": True,
        "RAG_ENABLE_RERANK": False,
        "RAG_ENABLE_DYNAMIC_TOP_K": False,
        "RAG_ENABLE_DYNAMIC_QUERY_BUDGET": False,
        "RAG_ENABLE_MMR_SELECTION": False,
        "RAG_ENABLE_SET_SELECTION": False,
        "RAG_ENABLE_EVIDENCE_TREE_SEARCH": False,
        "RAG_ENABLE_HAZARD_HINT_ROUTING": False,
        "RAG_ENABLE_TEXT_REPAIR": False,
        "RAG_TOP_K": 3,
    },
    "full_system_evidence_tree": {
        "RAG_RETRIEVAL_MODE": "hybrid",
        "RAG_ENABLE_QUERY_REWRITE": True,
        "RAG_QUERY_REWRITE_USE_LLM": False,  # disable LLM rewrite for offline reproducibility
        "RAG_ENABLE_DENSE_RETRIEVAL": True,
        "RAG_ENABLE_RERANK": True,
        "RAG_ENABLE_DYNAMIC_TOP_K": True,
        "RAG_ENABLE_DYNAMIC_QUERY_BUDGET": True,
        "RAG_ENABLE_MMR_SELECTION": True,
        "RAG_ENABLE_SET_SELECTION": True,
        "RAG_ENABLE_EVIDENCE_TREE_SEARCH": True,
        "RAG_ENABLE_HAZARD_HINT_ROUTING": True,
        "RAG_ENABLE_TEXT_REPAIR": True,
        "RAG_TOP_K": 5,
    },
    "full_system_offline": {
        "RAG_RETRIEVAL_MODE": "hybrid",
        "RAG_ENABLE_QUERY_REWRITE": True,
        "RAG_QUERY_REWRITE_USE_LLM": False,
        "RAG_ENABLE_DENSE_RETRIEVAL": True,
        "RAG_ENABLE_RERANK": False,
        "RAG_ENABLE_DYNAMIC_TOP_K": True,
        "RAG_ENABLE_DYNAMIC_QUERY_BUDGET": True,
        "RAG_ENABLE_MMR_SELECTION": True,
        "RAG_ENABLE_SET_SELECTION": True,
        "RAG_ENABLE_EVIDENCE_TREE_SEARCH": True,
        "RAG_ENABLE_HAZARD_HINT_ROUTING": True,
        "RAG_ENABLE_TEXT_REPAIR": True,
        "RAG_TOP_K": 5,
    },
}


def evaluate_profile(name: str, profile: Dict[str, Any], cases: List[Dict[str, Any]],
                     seeds: List[int]) -> Dict[str, Any]:
    """Run profile across seeds; collect per-seed metrics."""
    seed_runs: List[Dict[str, Any]] = []
    for seed in seeds:
        random.seed(seed)
        with temporary_settings(profile):
            top1_hits = 0
            top3_hits = 0
            mrrs: List[float] = []
            latencies: List[float] = []
            rows: List[Dict[str, Any]] = []
            for c in cases:
                t0 = perf_counter()
                try:
                    results = rule_retriever.retrieve(c["query"], scene=c["scene"], top_k=profile["RAG_TOP_K"])
                except Exception as e:
                    results = []
                lat_ms = (perf_counter() - t0) * 1000.0
                latencies.append(lat_ms)
                returned_ids = [r.get("id") or r.get("rule_id") for r in (results or [])]
                returned_ids = [x for x in returned_ids if x]
                h1 = hit_at_k(returned_ids, c["expected_ids"], 1)
                h3 = hit_at_k(returned_ids, c["expected_ids"], 3)
                rr = reciprocal_rank(returned_ids, c["expected_ids"])
                if h1: top1_hits += 1
                if h3: top3_hits += 1
                mrrs.append(rr)
                rows.append({
                    "name": c["name"],
                    "query": c["query"],
                    "scene": c["scene"],
                    "expected_ids": c["expected_ids"],
                    "returned_ids": returned_ids,
                    "hit_top1": h1,
                    "hit_top3": h3,
                    "rr": rr,
                    "latency_ms": round(lat_ms, 2),
                })
            seed_runs.append({
                "seed": seed,
                "top1": top1_hits / len(cases),
                "top3": top3_hits / len(cases),
                "mrr": sum(mrrs) / len(mrrs),
                "avg_latency_ms": round(mean(latencies), 2),
                "p95_latency_ms": round(percentile(latencies, 95), 2),
                "rows": rows,
            })

    # Aggregate
    top1s = [r["top1"] for r in seed_runs]
    top3s = [r["top3"] for r in seed_runs]
    mrrs_agg = [r["mrr"] for r in seed_runs]
    lat_avg = [r["avg_latency_ms"] for r in seed_runs]
    lat_p95 = [r["p95_latency_ms"] for r in seed_runs]

    return {
        "profile": name,
        "config": profile,
        "n_cases": len(cases),
        "n_seeds": len(seeds),
        "top1": {"per_seed": top1s, "mean": mean(top1s), "ci": bootstrap_ci(top1s)},
        "top3": {"per_seed": top3s, "mean": mean(top3s), "ci": bootstrap_ci(top3s)},
        "mrr":  {"per_seed": mrrs_agg, "mean": mean(mrrs_agg), "ci": bootstrap_ci(mrrs_agg)},
        "avg_latency_ms": {"per_seed": lat_avg, "mean": mean(lat_avg)},
        "p95_latency_ms": {"per_seed": lat_p95, "mean": mean(lat_p95)},
        "seed_runs": seed_runs,  # detailed
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    ap.add_argument("--json", default=str(DEFAULT_JSON))
    ap.add_argument("--max-cases", type=int, default=0)
    ap.add_argument("--seeds", default="20260427,42,2026")
    ap.add_argument("--profiles", default="all",
                    help="Comma-separated profile names or 'all'")
    args = ap.parse_args()

    cases = load_cases(Path(args.benchmark), max_cases=args.max_cases)
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    if args.profiles == "all":
        profile_names = list(PROFILES.keys())
    else:
        profile_names = [p.strip() for p in args.profiles.split(",") if p.strip()]

    print(f"Benchmark: {args.benchmark} ({len(cases)} cases)")
    print(f"Seeds: {seeds}")
    print(f"Profiles: {profile_names}")
    print()

    out: List[Dict[str, Any]] = []
    for name in profile_names:
        if name not in PROFILES:
            print(f"WARN: unknown profile {name}, skipping")
            continue
        print(f"--- Running profile: {name} ---")
        result = evaluate_profile(name, PROFILES[name], cases, seeds)
        # Print summary
        t1 = result["top1"]
        t3 = result["top3"]
        mr = result["mrr"]
        print(f"  Top1: {t1['mean']:.4f} (95% CI [{t1['ci']['lo']:.4f}, {t1['ci']['hi']:.4f}])")
        print(f"  Top3: {t3['mean']:.4f} (95% CI [{t3['ci']['lo']:.4f}, {t3['ci']['hi']:.4f}])")
        print(f"  MRR : {mr['mean']:.4f} (95% CI [{mr['ci']['lo']:.4f}, {mr['ci']['hi']:.4f}])")
        print(f"  Latency avg/P95: {result['avg_latency_ms']['mean']:.2f}ms / {result['p95_latency_ms']['mean']:.2f}ms")
        out.append(result)

    Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote: {args.json}")


if __name__ == "__main__":
    main()
