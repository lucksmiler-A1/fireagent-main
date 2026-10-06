# Fire Rules Knowledge Base

This directory stores the structured fire-safety knowledge used by FireAgent's RAG pipeline.

## Main File

- `fire_rules.json`: clause-level fire-safety rule base.
- `scene_guides.json`: scene-specific inspection guidance.
- `production_safety_playbook.json`: production-safety supplements for industrial and construction scenes.

## Purpose

The rule base turns free-form model output into evidence-grounded safety reasoning:

```text
visual facts
  -> query construction
  -> rule retrieval
  -> evidence set selection
  -> evidence-constrained answer
```

Each returned conclusion should be traceable to one or more rules whenever evidence is sufficient.

## Chunking Policy

- Method: manual article-level chunking.
- Target chunk size: 200-500 Chinese characters.
- Overlap: about 50 characters when a rule spans multiple semantic units.
- Clause IDs should remain stable across versions to support reproducible evaluation.

## Recommended Rule Fields

```json
{
  "id": "GB50016-EXAMPLE-001",
  "source": "GB 50016-2014(2018)",
  "article": "example article id",
  "title": "rule title",
  "content": "rule text",
  "scenes": ["campus", "residential", "industrial"],
  "hazards": ["electrical", "evacuation", "combustible"],
  "keywords": ["配电柜", "疏散通道", "可燃物"]
}
```

The actual JSON may include additional debug or retrieval fields. Retrieval robustness improves when both Chinese terms and stable English tags are present.

## Source Categories

The current knowledge base is organized around common fire-safety and safety-management sources, including:

- Building fire protection and evacuation rules.
- Fire extinguisher configuration rules.
- Sprinkler and facility-management rules.
- High-rise residential fire-safety management rules.
- Fire law and emergency-management guidance.
- Production-safety supplements for electrical boxes, temporary cables and construction scenes.

## Update Rule

When updating the knowledge base:

- Keep `id` / `article` stable whenever a rule is only edited, not replaced.
- Keep `source` normalized so source-diversity selection can work reliably.
- Add `scenes`, `hazards` and `keywords` for retrieval and evidence coverage.
- Avoid adding very long mixed-topic chunks; split them into smaller clause-level evidence units.
- Run retrieval evaluation after substantial changes.

## Relation to Algorithms

The rule base is consumed by:

- Hybrid retrieval: lexical, sparse vector and dense semantic matching.
- Evidence tree retrieval: main, scene and hazard query paths.
- Submodular evidence set selection: source diversity and hazard coverage.
- Open-set guardrail: candidate count, top score and coverage thresholds.
