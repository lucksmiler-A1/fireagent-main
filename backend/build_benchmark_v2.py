#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
base_path = ROOT / 'retrieval_benchmark.json'
out_path = ROOT / 'retrieval_benchmark_v2.json'

base = json.loads(base_path.read_text(encoding='utf-8'))
if not isinstance(base, list):
    raise ValueError('retrieval_benchmark.json must be a list')

hard_prompts = [
    '另外有人反馈消防演练记录也不全。',
    '顺便还担心应急预案是否有效。',
    '另一个同事提到设备维护也有问题。',
    '还有人说培训台账可能缺失。',
    '也有人怀疑巡查频次不够。',
    '补充：现场还有杂物堆放情况。',
    '另有意见说电气隐患更突出。',
    '同时担心报警系统故障。',
    '旁边人员还问开业前检查要求。',
    '管理层还想确认处罚条款。',
]

records = []
seen_names = set()
for idx, item in enumerate(base):
    if not isinstance(item, dict):
        continue
    name = str(item.get('name') or f'case_{idx}')
    query = str(item.get('query') or '').strip()
    scene = str(item.get('scene') or 'campus')
    expected = list(item.get('expected_ids') or [])
    if not query or not expected:
        continue

    if name not in seen_names:
        records.append({
            'name': name,
            'scene': scene,
            'query': query,
            'expected_ids': expected,
        })
        seen_names.add(name)

    distractor = hard_prompts[idx % len(hard_prompts)]
    hard_query = (
        f"{query} {distractor} "
        "请先聚焦前一个问题，给出法规依据，并用1-2条最关键条款回答。"
    )
    hard_name = f"{name}_hard"
    if hard_name not in seen_names:
        records.append({
            'name': hard_name,
            'scene': scene,
            'query': hard_query,
            'expected_ids': expected,
        })
        seen_names.add(hard_name)

out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'base_cases={len(base)} expanded_cases={len(records)} path={out_path}')
