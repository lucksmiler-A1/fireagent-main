#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Dict, Iterable, List, Sequence

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.retriever import rule_retriever

DEFAULT_BENCHMARK = ROOT / "retrieval_benchmark_large_v1.json"
DEFAULT_JSON = ROOT / "experiments_publication_baselines.json"
RULES_FILE = ROOT / "app" / "data" / "fire_rules.json"


def load_cases(path: Path, max_cases: int = 0) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
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
                "name": str(item.get("name") or f"case_{len(cases)}").strip(),
                "query": query,
                "scene": scene,
                "expected_ids": expected_ids,
            }
        )
        if max_cases > 0 and len(cases) >= max_cases:
            break
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


def reciprocal_rank(found_ids: Sequence[str], expected_ids: Sequence[str]) -> float:
    expected = set(expected_ids)
    for idx, rule_id in enumerate(found_ids, start=1):
        if rule_id in expected:
            return 1.0 / idx
    return 0.0


def bootstrap_ci(values: Sequence[float], iterations: int = 1000, seed: int = 20260427) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "low": 0.0, "high": 0.0}
    rng = random.Random(seed)
    n = len(values)
    samples = []
    for _ in range(max(iterations, 1)):
        samples.append(mean(values[rng.randrange(n)] for _ in range(n)))
    samples.sort()
    low_idx = int(0.025 * (len(samples) - 1))
    high_idx = int(0.975 * (len(samples) - 1))
    return {
        "mean": round(mean(values), 4),
        "low": round(samples[low_idx], 4),
        "high": round(samples[high_idx], 4),
    }


def summarize_rows(profile: str, rows: List[Dict[str, Any]], latency_ms: List[float]) -> Dict[str, Any]:
    top1_values = [1.0 if r["hit_top1"] else 0.0 for r in rows]
    top3_values = [1.0 if r["hit_top3"] else 0.0 for r in rows]
    mrr_values = [float(r["mrr"]) for r in rows]
    sorted_latency = sorted(latency_ms)
    p95_idx = int(round(0.95 * (len(sorted_latency) - 1))) if sorted_latency else 0
    return {
        "profile": profile,
        "case_count": len(rows),
        "top1_hit_rate": round(mean(top1_values), 4) if rows else 0.0,
        "top3_hit_rate": round(mean(top3_values), 4) if rows else 0.0,
        "mrr": round(mean(mrr_values), 4) if rows else 0.0,
        "top1_ci95": bootstrap_ci(top1_values),
        "top3_ci95": bootstrap_ci(top3_values),
        "mrr_ci95": bootstrap_ci(mrr_values),
        "avg_latency_ms": round(mean(latency_ms), 2) if latency_ms else 0.0,
        "p95_latency_ms": round(sorted_latency[p95_idx], 2) if sorted_latency else 0.0,
        "rows": rows,
    }


def evaluate_retrieval_profile(
    name: str,
    cases: List[Dict[str, Any]],
    overrides: Dict[str, Any],
    top_k: int,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    latency_ms: List[float] = []
    with temporary_settings(overrides):
        for case in cases:
            begin = perf_counter()
            result = rule_retriever.retrieve_with_debug(case["query"], case["scene"], top_k=max(top_k, 3))
            elapsed = (perf_counter() - begin) * 1000.0
            latency_ms.append(elapsed)
            returned_ids = [str(item.get("id", "")) for item in result.get("rules", [])]
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
    report = summarize_rows(name, rows, latency_ms)
    report["overrides"] = overrides
    return report


def build_rule_aliases() -> Dict[str, List[str]]:
    aliases: Dict[str, List[str]] = {}
    if not RULES_FILE.exists():
        return aliases
    raw = json.loads(RULES_FILE.read_text(encoding="utf-8-sig"))
    rules = raw.get("rules", []) if isinstance(raw, dict) else []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("id", "")).strip()
        if not rule_id:
            continue
        source = str(rule.get("source", "")).strip()
        article = str(rule.get("article", "")).strip()
        title = str(rule.get("title", "")).strip()
        values = {rule_id, rule_id.lower(), rule_id.replace("-", ""), rule_id.replace("-", " ")}
        if source:
            values.add(source)
        if article:
            values.add(article)
            values.add(f"第{article}条")
            values.add(f"article {article}".lower())
            if source:
                values.add(f"{source} {article}")
        if title:
            values.add(title.lower())
        if rule_id.startswith("FIRELAW-"):
            suffix = rule_id.split("-", 1)[1]
            values.update({
                f"消防法第{suffix}条",
                f"中华人民共和国消防法第{suffix}条",
                f"消防法{suffix}条",
                f"fire law article {suffix}",
                f"article {suffix}",
            })
            if suffix == "28":
                values.update({"消防法第二十八条", "中华人民共和国消防法第二十八条"})
        if rule_id.startswith("HMBF-"):
            suffix = rule_id.split("-", 1)[1]
            values.update({
                f"高层民用建筑消防安全管理规定第{suffix}条",
                f"高层民用建筑第{suffix}条",
            })
            if suffix == "37":
                values.update({
                    "高层民用建筑消防安全管理规定第三十七条",
                    "高层民用建筑第三十七条",
                })
            if suffix == "47-7":
                values.update({
                    "高层民用建筑消防安全管理规定第四十七条第七项",
                    "高层民用建筑第四十七条第七项",
                })
        aliases[rule_id] = sorted(v for v in values if v)
    return aliases


def normalize_rule_text(text: str) -> str:
    normalized = (text or "").lower()
    normalized = re.sub(r"[《》〈〉“”\"'`，。；：、,.()\[\]（）\s-]+", "", normalized)
    return normalized


def extract_rule_ids_from_text(text: str, aliases: Dict[str, List[str]]) -> List[str]:
    normalized = (text or "").lower()
    compact = normalize_rule_text(normalized)
    hits: List[str] = []
    for rule_id, names in aliases.items():
        for alias in names:
            a = alias.lower()
            if a and (a in normalized or normalize_rule_text(a) in compact):
                hits.append(rule_id)
                break
    return hits


def canonical_rule_ids(
    raw_ids: Sequence[Any],
    content: str,
    aliases: Dict[str, List[str]],
    allowed_ids: set[str] | None = None,
) -> List[str]:
    hits: List[str] = []
    alias_keys = set(aliases)
    for raw_id in raw_ids:
        value = str(raw_id).strip()
        if not value:
            continue
        if value in alias_keys:
            hits.append(value)
        else:
            hits.extend(extract_rule_ids_from_text(value, aliases))
    hits.extend(extract_rule_ids_from_text(content, aliases))
    if allowed_ids is not None:
        hits = [rule_id for rule_id in hits if rule_id in allowed_ids]
    return list(dict.fromkeys(hits))


def refresh_cached_row(row: Dict[str, Any], aliases: Dict[str, List[str]]) -> Dict[str, Any]:
    refreshed = dict(row)
    parsed = refreshed.get("parsed")
    raw_ids: List[Any] = []
    if isinstance(parsed, dict):
        raw_ids = list(parsed.get("rule_ids", []) or [])
    allowed = set(refreshed.get("evidence_ids") or []) or None
    returned_ids = canonical_rule_ids(raw_ids, str(refreshed.get("raw_content") or ""), aliases, allowed)
    expected = set(str(x) for x in (refreshed.get("expected_ids") or []))
    refreshed["returned_ids"] = returned_ids
    refreshed["hit_top1"] = bool(returned_ids[:1] and returned_ids[0] in expected)
    refreshed["hit_top3"] = any(rule_id in expected for rule_id in returned_ids[:3])
    refreshed["mrr"] = reciprocal_rank(returned_ids, refreshed.get("expected_ids") or [])
    return refreshed


def call_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout: float,
) -> str:
    endpoint = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 512,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    return str(data["choices"][0]["message"]["content"])


def evaluate_direct_model(
    cases: List[Dict[str, Any]],
    base_url: str,
    api_key: str,
    model: str,
    timeout: float,
    sleep_seconds: float,
    cache_path: Path | None = None,
) -> Dict[str, Any]:
    aliases = build_rule_aliases()
    rows: List[Dict[str, Any]] = []
    latency_ms: List[float] = []
    cached: Dict[str, Dict[str, Any]] = {}
    if cache_path and cache_path.exists():
        raw_cache = json.loads(cache_path.read_text(encoding="utf-8-sig"))
        if isinstance(raw_cache, list):
            cached = {str(item.get("name", "")): item for item in raw_cache if isinstance(item, dict)}
    system = (
        "You are a fire-safety inspection assistant. Answer directly without retrieval. "
        "Return strict JSON with keys: risk_level, rule_ids, should_refuse, answer. "
        "If evidence is insufficient, set should_refuse=true."
    )
    for idx, case in enumerate(cases, start=1):
        user = (
            f"Scene: {case['scene']}\n"
            f"Question: {case['query']}\n"
            "Give the most relevant legal/regulatory basis if you know it."
        )
        if case["name"] in cached:
            cached_row = refresh_cached_row(cached[case["name"]], aliases)
            rows.append(cached_row)
            latency_ms.append(float(cached_row.get("latency_ms", 0.0)))
            continue

        begin = perf_counter()
        try:
            content = call_openai_compatible(
                base_url=base_url,
                api_key=api_key,
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                timeout=timeout,
            )
            error = ""
        except Exception as exc:  # noqa: BLE001 - keep baseline runner robust
            content = ""
            error = str(exc)
        elapsed = (perf_counter() - begin) * 1000.0
        latency_ms.append(elapsed)

        raw_ids: List[Any] = []
        parsed: Any = None
        if content:
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    raw_ids = list(parsed.get("rule_ids", []) or [])
            except json.JSONDecodeError:
                parsed = None
        returned_ids = canonical_rule_ids(raw_ids, content, aliases)
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
                "mrr": reciprocal_rank(returned_ids, case["expected_ids"]),
                "latency_ms": round(elapsed, 2),
                "raw_content": content,
                "parsed": parsed,
                "error": error,
            }
        )
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        if sleep_seconds > 0 and idx < len(cases):
            time.sleep(sleep_seconds)
    return summarize_rows(f"direct_model_no_rag:{model}", rows, latency_ms)


def evaluate_rag_model(
    cases: List[Dict[str, Any]],
    base_url: str,
    api_key: str,
    model: str,
    retrieval_overrides: Dict[str, Any],
    top_k: int,
    timeout: float,
    sleep_seconds: float,
    cache_path: Path | None = None,
) -> Dict[str, Any]:
    aliases = build_rule_aliases()
    rows: List[Dict[str, Any]] = []
    latency_ms: List[float] = []
    cached: Dict[str, Dict[str, Any]] = {}
    if cache_path and cache_path.exists():
        raw_cache = json.loads(cache_path.read_text(encoding="utf-8-sig"))
        if isinstance(raw_cache, list):
            cached = {str(item.get("name", "")): item for item in raw_cache if isinstance(item, dict)}

    system = (
        "You are a fire-safety inspection assistant using only the provided evidence. "
        "Return strict JSON with keys: risk_level, rule_ids, should_refuse, answer. "
        "rule_ids must be selected from the provided evidence ids only. "
        "If the evidence does not support a conclusion, set should_refuse=true."
    )

    with temporary_settings(retrieval_overrides):
        for idx, case in enumerate(cases, start=1):
            if case["name"] in cached:
                cached_row = refresh_cached_row(cached[case["name"]], aliases)
                rows.append(cached_row)
                latency_ms.append(float(cached_row.get("latency_ms", 0.0)))
                continue

            begin = perf_counter()
            retrieval = rule_retriever.retrieve_with_debug(case["query"], case["scene"], top_k=max(top_k, 3))
            evidence_rules = retrieval.get("rules", [])[:top_k]
            evidence = "\n".join(
                f"- id: {r.get('id')}; title: {r.get('title')}; text: {r.get('text')}"
                for r in evidence_rules
            )
            user = (
                f"Scene: {case['scene']}\n"
                f"Question: {case['query']}\n"
                f"Evidence:\n{evidence}\n"
                "Choose the most relevant evidence ids and answer briefly."
            )
            try:
                content = call_openai_compatible(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    timeout=timeout,
                )
                error = ""
            except Exception as exc:  # noqa: BLE001 - keep baseline runner robust
                content = ""
                error = str(exc)
            elapsed = (perf_counter() - begin) * 1000.0
            latency_ms.append(elapsed)

            parsed: Any = None
            raw_ids: List[Any] = []
            evidence_ids = {str(r.get("id", "")) for r in evidence_rules}
            if content:
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        raw_ids = list(parsed.get("rule_ids", []) or [])
                except json.JSONDecodeError:
                    parsed = None
            returned_ids = canonical_rule_ids(raw_ids, content, aliases, evidence_ids)
            expected = set(case["expected_ids"])
            rows.append(
                {
                    "name": case["name"],
                    "scene": case["scene"],
                    "query": case["query"],
                    "expected_ids": case["expected_ids"],
                    "evidence_ids": [str(r.get("id", "")) for r in evidence_rules],
                    "returned_ids": returned_ids,
                    "hit_top1": bool(returned_ids[:1] and returned_ids[0] in expected),
                    "hit_top3": any(rule_id in expected for rule_id in returned_ids[:3]),
                    "mrr": reciprocal_rank(returned_ids, case["expected_ids"]),
                    "latency_ms": round(elapsed, 2),
                    "raw_content": content,
                    "parsed": parsed,
                    "error": error,
                }
            )
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            if sleep_seconds > 0 and idx < len(cases):
                time.sleep(sleep_seconds)
    return summarize_rows(f"rag_model_standard_topk:{model}", rows, latency_ms)


def print_summary(report: Dict[str, Any]) -> None:
    print(f"[{report['profile']}]")
    print(f"cases={report['case_count']}")
    print(
        "top1={:.2%} (95% CI {:.2%}-{:.2%})".format(
            report["top1_hit_rate"], report["top1_ci95"]["low"], report["top1_ci95"]["high"]
        )
    )
    print(
        "top3={:.2%} (95% CI {:.2%}-{:.2%})".format(
            report["top3_hit_rate"], report["top3_ci95"]["low"], report["top3_ci95"]["high"]
        )
    )
    print(
        "mrr={:.4f} (95% CI {:.4f}-{:.4f})".format(
            report["mrr"], report["mrr_ci95"]["low"], report["mrr_ci95"]["high"]
        )
    )
    print(f"avg_latency_ms={report['avg_latency_ms']:.2f}")
    print(f"p95_latency_ms={report['p95_latency_ms']:.2f}")
    print("")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run publication-oriented baselines with CIs.")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--run-direct-model", action="store_true")
    parser.add_argument("--run-rag-model", action="store_true")
    parser.add_argument("--direct-base-url", default=os.getenv("EXTERNAL_LLM_BASE_URL", ""))
    parser.add_argument("--direct-api-key-env", default="EXTERNAL_LLM_API_KEY")
    parser.add_argument("--direct-model", default=os.getenv("EXTERNAL_LLM_MODEL", ""))
    parser.add_argument("--direct-timeout", type=float, default=60.0)
    parser.add_argument("--direct-sleep", type=float, default=0.0)
    parser.add_argument("--direct-cache", type=Path, default=ROOT / "experiments_direct_model_cache.json")
    parser.add_argument("--rag-cache", type=Path, default=ROOT / "experiments_rag_model_cache.json")
    args = parser.parse_args(list(argv) if argv is not None else None)

    cases = load_cases(args.benchmark, max_cases=args.max_cases)
    reports: List[Dict[str, Any]] = []

    standard_single_rag = {
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
    }
    full_method = {
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

    for name, overrides in [
        ("B_standard_single_rag_keyword_topk", standard_single_rag),
        ("Ours_full_method_local", full_method),
    ]:
        report = evaluate_retrieval_profile(name, cases, overrides, top_k=args.top_k)
        reports.append(report)
        print_summary(report)

    if args.run_direct_model:
        api_key = os.getenv(args.direct_api_key_env, "")
        if not api_key or not args.direct_base_url or not args.direct_model:
            raise SystemExit(
                "Direct model baseline requires --direct-base-url, --direct-model, "
                f"and env var {args.direct_api_key_env}."
            )
        report = evaluate_direct_model(
            cases=cases,
            base_url=args.direct_base_url,
            api_key=api_key,
            model=args.direct_model,
            timeout=args.direct_timeout,
            sleep_seconds=args.direct_sleep,
            cache_path=args.direct_cache,
        )
        reports.append(report)
        print_summary(report)

    if args.run_rag_model:
        api_key = os.getenv(args.direct_api_key_env, "")
        if not api_key or not args.direct_base_url or not args.direct_model:
            raise SystemExit(
                "RAG model baseline requires --direct-base-url, --direct-model, "
                f"and env var {args.direct_api_key_env}."
            )
        report = evaluate_rag_model(
            cases=cases,
            base_url=args.direct_base_url,
            api_key=api_key,
            model=args.direct_model,
            retrieval_overrides=standard_single_rag,
            top_k=args.top_k,
            timeout=args.direct_timeout,
            sleep_seconds=args.direct_sleep,
            cache_path=args.rag_cache,
        )
        reports.append(report)
        print_summary(report)

    args.json.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved={args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
