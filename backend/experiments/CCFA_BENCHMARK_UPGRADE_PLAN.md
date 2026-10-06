# CCF-A Driven Benchmark Upgrade Plan (2026-04-19)

This document maps recent CCF-A papers to executable benchmark upgrades in this project.

## 1) Targeted CCF-A Methods and Local Mapping

1. Evidence Tree Search (ACL 2025)
- Paper: https://aclanthology.org/2025.acl-long.148/
- Local switch: `RAG_ENABLE_EVIDENCE_TREE_SEARCH`
- Benchmark action: include multi-intent compound queries and evaluate Top-3 hit + MRR under distractions.

2. Set Selection for RAG / SetR (ACL 2025)
- Paper: https://aclanthology.org/2025.acl-long.861/
- Local switch: `RAG_ENABLE_SET_SELECTION`
- Benchmark action: evaluate retrieval diversity and top-k stability across paraphrases.

3. Dynamic Retrieval (DioR, ACL 2025)
- Paper: https://aclanthology.org/2025.acl-long.628/
- Local switch: `RAG_ENABLE_DYNAMIC_QUERY_BUDGET`
- Benchmark action: evaluate hit-rate vs latency trade-off.

4. ODE Open-set Hallucination Eval (CVPR 2025)
- Paper: https://openaccess.thecvf.com/content/CVPR2025/html/Tu_ODE_Open-Set_Evaluation_of_Hallucinations_in_Multimodal_Large_Language_Models_CVPR_2025_paper.html
- Local protocol: `retrieval_benchmark_open_set_v1.json` + `eval_open_set_guardrail.py`
- Benchmark action: refusal precision/recall and false-accept count.

5. MissRAG Missing Modality (ICCV 2025)
- Paper: https://openaccess.thecvf.com/content/ICCV2025/html/Pipoli_MissRAG_Addressing_the_Missing_Modality_Challenge_in_Multimodal_Large_Language_Models_ICCV_2025_paper.html
- Local protocol: add occlusion/blur/noise style prompts in blind split; compare degradation.

6. C-3PO Multi-agent RAG (ICML 2025)
- Paper: https://proceedings.mlr.press/v267/chen25an.html
- Local module: planner + retriever + compliance + reporter flow in `agent.py`
- Benchmark action: tool-routing correctness and end-to-end latency.

## 2) Extra CCF-A References for Next Iteration

1. Adaptive Retrieval without Self-Knowledge (ACL 2025)
- Paper: https://aclanthology.org/2025.acl-long.926/
- Why: can drive uncertainty-triggered retrieval depth and reduce over-retrieval.

2. Speculative RAG (ICLR 2025)
- Paper: https://proceedings.iclr.cc/paper_files/paper/2025/hash/2ea06b52f613716e67458f5ab3fb7558-Abstract-Conference.html
- Why: can reduce average Stage2 latency by parallel candidate generation + verification.

## 3) Public Testset Pool Used for Expansion

Machine-readable registry: `app/data/public_testsets_manifest.json`

Included sources:
- D-Fire: https://github.com/gaia-solutions-on-demand/DFireDataset
- MIVIA Fire Detection: https://mivia.unisa.it/datasets/video-analysis-datasets/fire-detection-dataset/
- ONFIRE 2025: https://mivia.unisa.it/onfire2025/
- SHWD: https://github.com/njvisionpower/Safety-Helmet-Wearing-Dataset
- SH17: https://github.com/ahmadmughees/SH17dataset
- Open Images V7: https://storage.googleapis.com/openimages/web/factsfigures_v7.html
- DetectiumFire: https://arxiv.org/abs/2511.02495
- MmodalFire: https://www.nature.com/articles/s41597-026-06810-6

## 4) Repro Commands

```bash
# build larger positive benchmark + open-set benchmark
python build_large_benchmark.py --target-size 600 --open-set-size 160

# build blind split from larger positive benchmark
python build_blind_benchmark.py --input retrieval_benchmark_large_v1.json --output retrieval_benchmark_large_blind_v1.json

# profile matrix on large dev + large blind
python eval_profile_matrix.py --dev retrieval_benchmark_large_v1.json --blind retrieval_benchmark_large_blind_v1.json --json experiments_profile_matrix_large_v1.json

# open-set refusal protocol
python eval_open_set_guardrail.py --benchmark retrieval_benchmark_open_set_v1.json --json experiments_open_set_guardrail_v1.json
```

## 5) Expected Reporting Metrics (Paper-ready)

- Retrieval quality: Top1 / Top3 / MRR
- Efficiency: Avg latency / P95 latency
- Robustness: blind split drop ratio
- Safety: refusal precision / refusal recall / false accept count
- (Optional stage1 image side) detection metrics: mAP / F1 on external image datasets
