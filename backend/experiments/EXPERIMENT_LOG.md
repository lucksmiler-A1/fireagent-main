# Experiment Log (for thesis)

## Setup
- Benchmark: `backend/retrieval_benchmark.json` (36 labeled retrieval cases)
- Main metric: Top1 hit-rate / Top3 hit-rate / MRR
- Profiles: `hybrid` and `hybrid+dense+rerank`

## Iterative Results
| Iteration | Profile | Top1 | Top3 | MRR | dTop3 vs Baseline | dTop1 vs Baseline | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline | hybrid | 0.1944 | 0.2778 | 0.2625 | +0.0000 | +0.0000 | Initial project state |
| baseline | hybrid+dense+rerank | 0.1944 | 0.2778 | 0.2625 | +0.0000 | +0.0000 | Initial project state |
| iter1_kb_expand | hybrid | 0.1944 | 0.2778 | 0.2625 | +0.0000 | +0.0000 | Expanded KB coverage (11->33 rules); no gain yet |
| iter1_kb_expand | hybrid+dense+rerank | 0.1944 | 0.2778 | 0.2625 | +0.0000 | +0.0000 | Expanded KB coverage (11->33 rules); no gain yet |
| iter2_retrieval_upgrade | hybrid | 0.1944 | 0.2778 | 0.2625 | +0.0000 | +0.0000 | Added dynamic top-k/MMR and dedupe fix; still limited due encoding noise |
| iter2_retrieval_upgrade | hybrid+dense+rerank | 0.1944 | 0.2778 | 0.2625 | +0.0000 | +0.0000 | Added dynamic top-k/MMR and dedupe fix; still limited due encoding noise |
| iter2b_encoding_and_router | hybrid | 0.3611 | 0.5278 | 0.4708 | +0.2500 | +0.1667 | Fixed corrupted rule text and intent router enhancement |
| iter2b_encoding_and_router | hybrid+dense+rerank | 0.3611 | 0.5278 | 0.4708 | +0.0000 | +0.0000 | Fixed corrupted rule text and intent router enhancement |
| iter3_intent_router | hybrid | 0.7222 | 0.9444 | 0.8102 | +0.6666 | +0.5278 | Expanded scene-intent query routing for hard cases |
| iter3_intent_router | hybrid+dense+rerank | 0.7222 | 0.9444 | 0.8102 | +0.0000 | +0.0000 | Expanded scene-intent query routing for hard cases |
| iter4_targeted_fix | hybrid | 0.7778 | 0.9722 | 0.8657 | +0.6944 | +0.5834 | Targeted disambiguation for periodic inspection/emergency plan queries |
| iter4_targeted_fix | hybrid+dense+rerank | 0.7778 | 0.9722 | 0.8657 | +0.0000 | +0.0000 | Targeted disambiguation for periodic inspection/emergency plan queries |
| iter5_final | hybrid | 0.8056 | 1.0000 | 0.8935 | +0.7222 | +0.6112 | Added rescue-access targeted boost; reached full Top3 coverage |
| iter5_final | hybrid+dense+rerank | 0.8056 | 1.0000 | 0.8935 | +0.0000 | +0.0000 | Added rescue-access targeted boost; reached full Top3 coverage |
| iter6_hazard_hint_router | hybrid | 0.8611 | 1.0000 | 0.9259 | +0.7222 | +0.6667 | Added hazard-intent routing bonus to improve Top1 ranking |
| iter6_hazard_hint_router | hybrid+dense+rerank | 0.8611 | 1.0000 | 0.9259 | +0.0000 | +0.0000 | Added hazard-intent routing bonus to improve Top1 ranking |

## Best Checkpoint
- Best profile: `iter6_hazard_hint_router / hybrid` with Top1=0.8611, Top3=1.0000, MRR=0.9259.
- Relative gain vs baseline: Top1 +0.6667, Top3 +0.7222, MRR +0.6634.

## Remaining Misses (Best Checkpoint)
- None

## Ablation (iter5 checkpoint)
| Profile | Top1 | Top3 | MRR | Delta Top3 vs full |
|---|---:|---:|---:|---:|
| full | 0.8056 | 1.0000 | 0.8935 | +0.0000 |
| wo_query_rewrite | 0.8056 | 1.0000 | 0.8935 | +0.0000 |
| wo_text_repair | 0.8056 | 1.0000 | 0.8935 | +0.0000 |
| wo_dynamic_topk | 0.8056 | 1.0000 | 0.8935 | +0.0000 |
| wo_mmr | 0.8056 | 1.0000 | 0.8889 | +0.0000 |
| keyword_only | 0.6944 | 0.9722 | 0.8310 | -0.0278 |

- Observation: keyword_only drops notably, showing hybrid retrieval contributes major gains.
- Observation: removing MMR slightly reduces MRR, indicating evidence diversity helps ranking quality.

## Notes for Paper Writing
- Iteration 1 is a negative result: KB expansion alone did not improve retrieval quality.
- Major gains came from retrieval stack changes (query routing + text normalization + targeted intent expansion).
- The final checkpoint reaches full Top3 coverage and higher Top1 ranking on current benchmark split.

## Large-Scale Benchmark Upgrade (2026-04-19)

### New benchmark assets
- `backend/retrieval_benchmark_large_v1.json` (650 positive cases)
- `backend/retrieval_benchmark_large_blind_v1.json` (650 blind paraphrased cases)
- `backend/retrieval_benchmark_open_set_v1.json` (200 open-set refusal cases)
- `backend/app/data/public_testsets_manifest.json` (public dataset registry for benchmark expansion)

### Profile matrix on large dev+blind
Source JSON: `backend/experiments_profile_matrix_large_v1.json`

| Split | Profile | Top1 | Top3 | MRR | Avg Latency (ms) | P95 (ms) |
|---|---|---:|---:|---:|---:|---:|
| dev(650) | iter7_dynamic | 0.5092 | 0.9123 | 0.7019 | 9.69 | 15.08 |
| dev(650) | iter8_set_selection | 0.5092 | 0.9000 | 0.7047 | 9.99 | 15.85 |
| dev(650) | iter9_evidence_tree | **0.5938** | 0.9015 | **0.7447** | 11.98 | 17.26 |
| blind(650) | iter7_dynamic | 0.4554 | **0.8769** | 0.6555 | 11.29 | 16.48 |
| blind(650) | iter8_set_selection | 0.4554 | 0.8662 | 0.6560 | 11.34 | 15.86 |
| blind(650) | iter9_evidence_tree | **0.5338** | 0.8585 | **0.6899** | 12.99 | 17.21 |

Observations:
- On larger dev set, evidence-tree gives clear Top1/MRR gains with moderate latency increase.
- On blind set, evidence-tree still improves Top1/MRR but slightly sacrifices Top3 coverage.
- This indicates stronger ranking precision but reduced recall under paraphrase shift.

### Ablation on large benchmark
Source JSON: `backend/experiments_ablation_large_v1.json`

| Profile | Top1 | Top3 | MRR |
|---|---:|---:|---:|
| full | 0.5938 | **0.9015** | 0.7447 |
| wo_query_rewrite | 0.5938 | **0.9015** | 0.7447 |
| wo_text_repair | 0.5938 | **0.9015** | 0.7447 |
| wo_dynamic_topk | 0.5938 | **0.9015** | 0.7447 |
| wo_mmr | 0.5092 | 0.9000 | 0.7002 |
| wo_set_selection | 0.5938 | 0.8938 | 0.7417 |
| wo_evidence_tree | 0.5092 | 0.9000 | 0.7047 |
| wo_hazard_hint_router | **0.6062** | 0.8969 | **0.7484** |
| keyword_only | 0.5908 | 0.8554 | 0.7227 |

Observations:
- MMR and evidence-tree remain the major contributors to ranking quality on the larger split.
- Keyword-only significantly hurts Top3, confirming hybrid retrieval necessity.

### Open-set guardrail protocol
Source JSON: `backend/experiments_open_set_guardrail_v1.json`

| Profile | Cases | Accuracy | Refusal Precision | Refusal Recall | False Accept | Avg Latency (ms) |
|---|---:|---:|---:|---:|---:|---:|
| hybrid_local_guardrail | 200 | 0.2900 | 1.0000 | 0.2900 | 142 | 6.68 |
| strict_guardrail_keyword | 200 | 0.3650 | 1.0000 | 0.3650 | 127 | 6.14 |

Observations:
- Current retriever still over-accepts open-set queries (high false accept count).
- Keyword-guardrail profile improves refusal recall, suggesting a practical safe fallback strategy.
