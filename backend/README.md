# FireAgent Backend

FastAPI backend for FireAgent, a knowledge-enhanced multimodal fire-safety inspection agent.

The backend implements the full analysis loop:

```text
image upload
  -> result cache
  -> Stage1 visual fact extraction
  -> scene-aware RAG retrieval
  -> evidence tree aggregation
  -> submodular evidence set selection
  -> open-set guardrail
  -> Stage2 evidence-constrained reasoning
  -> records, memory and insights
```

## Core Modules

```text
backend/
├── app/
│   ├── main.py                    # FastAPI entrypoint and static web mount
│   ├── api/
│   │   ├── routes.py              # API router aggregation
│   │   └── v1/                    # analysis, records, agent, memory APIs
│   ├── core/
│   │   ├── config.py              # model, RAG, memory and guardrail settings
│   │   └── cors.py
│   ├── data/
│   │   ├── fire_rules.json        # structured fire-safety rule base
│   │   ├── scene_guides.json      # scene-specific inspection hints
│   │   └── production_safety_playbook.json
│   ├── db/
│   │   ├── models.py              # SQLAlchemy entities
│   │   ├── schemas.py             # Pydantic schemas
│   │   └── crud.py                # persistence and query helpers
│   └── services/
│       ├── analyzer.py            # two-hop image analysis
│       ├── retriever.py           # hybrid RAG and evidence tree
│       ├── guardrail.py           # open-set conservative policy
│       ├── agent.py               # planner and tool routing
│       └── memory/                # core/task/short-term/long-term memory
├── eval_*.py                      # ablation and benchmark scripts
└── requirements.txt
```

## Requirements

- Python 3.10+
- SQLite, used by default through SQLAlchemy
- Optional SiliconFlow API key for real multimodal / LLM calls

Install dependencies:

```powershell
cd backend
pip install -r requirements.txt
```

Optional API key:

```powershell
$env:SILICONFLOW_API_KEY="your_api_key"
```

When the key is absent, deterministic fallback logic keeps the local demo and API shape usable.

## Run

```powershell
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

Then open:

- API docs: `http://127.0.0.1:8010/docs`
- Health check: `http://127.0.0.1:8010/health`
- Static Web demo: `http://127.0.0.1:8010/web/`

## Main APIs

All versioned APIs use the `/api/v1` prefix.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/analysis/upload` | Upload image and run full two-hop analysis |
| `GET` | `/records` | List historical analysis records |
| `GET` | `/records/{record_id}` | Fetch one analysis record |
| `GET` | `/records/insights` | Aggregate risk trends and recurring hazards |
| `POST` | `/records/clear` | Clear records and analysis cache |
| `POST` | `/agent/chat` | Planner-driven safety inspection chat |
| `GET` | `/memory/snapshot` | Export four-layer memory state |
| `GET` | `/memory/overview` | Query memory tasks and risk profile overview |
| `GET` | `/scene-guides` | Get scene-aware inspection guidance |

Example upload:

```powershell
curl.exe -X POST "http://127.0.0.1:8010/api/v1/analysis/upload" `
  -F "file=@C:\path\to\fire_hazard.jpg" `
  -F "scene=campus"
```

## Algorithmic Configuration

The major research switches are configured in `app/core/config.py`.

| Setting | Meaning |
| --- | --- |
| `RAG_RETRIEVAL_MODE` | `keyword`, `vector` or `hybrid` retrieval |
| `RAG_ENABLE_DENSE_RETRIEVAL` | Enable dense semantic retrieval |
| `RAG_ENABLE_RERANK` | Enable reranker-stage reordering |
| `RAG_ENABLE_DYNAMIC_QUERY_BUDGET` | Adapt retrieval budget to query complexity |
| `RAG_ENABLE_SET_SELECTION` | Enable evidence set selection |
| `RAG_ENABLE_EVIDENCE_TREE_SEARCH` | Enable multi-path evidence tree aggregation |
| `RAG_ENABLE_HAZARD_HINT_ROUTING` | Add hazard-type-aware routing and bonus |
| `LONG_MEMORY_ENABLE_EMBEDDING` | Enable long-term memory semantic retrieval |

## Evaluation

Representative scripts:

```powershell
cd backend

python eval_ablation.py
python eval_retrieval.py
python eval_open_set_guardrail.py
python eval_publication_baselines.py
python eval_publication_strong_baselines.py
```

Main evaluation dimensions:

- `Top-1`, `Top-3`, `MRR` for rule retrieval quality.
- Average and P95 latency for online feasibility.
- Refusal precision / recall for open-set guardrail behavior.
- Direct LLM, ordinary RAG and FireAgent variants for baseline comparison.

## Notes

This backend is a research prototype. It is designed for algorithm verification, controlled experiments and local demos. Fire-safety decisions in real deployments still require professional inspection and compliance review.
