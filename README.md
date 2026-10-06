# FireAgent

> Knowledge-enhanced multimodal agent for fire-safety hazard image analysis.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](#quick-start)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)](backend/README.md)
[![RAG](https://img.shields.io/badge/RAG-evidence--tree-orange)](docs/ALGORITHMS.md)
[![Guardrail](https://img.shields.io/badge/Safety-open--set%20guardrail-bb1d1d)](docs/ALGORITHMS.md#8-open-set-guardrail)
[![License: MIT](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

FireAgent 是一个面向消防安全巡检的多模态智能体系统。它不是简单地把图片丢给大模型生成结论，而是将 **视觉事实抽取、消防法规 RAG、证据树检索、开放集守护与四层记忆机制** 串成一条可解释、可审计、可持续治理的安全分析链路。

一句话概括：**先看清现场，再检索依据，最后基于证据给出风险判断和整改建议。**

## At a Glance

| Dimension | Design |
| --- | --- |
| Task | Fire-safety hazard image analysis |
| Core method | Two-hop inference + evidence-tree RAG + open-set guardrail |
| Knowledge base | Structured fire-safety rules, scene guides and production-safety playbooks |
| Backend | FastAPI, SQLAlchemy, SQLite, modular services |
| Frontend | Static Web demo and WeChat Mini Program |
| Evaluation | Retrieval ablation, strong baselines, open-set guardrail benchmark |
| Output | Risk level, hazard explanation, cited evidence, corrective actions and history |

## Why FireAgent

消防隐患识别不是普通图像分类任务。真实巡检场景中，一张图片可能同时包含通道堵塞、电气隐患、可燃物堆放、设备遮挡等多类风险；如果直接让大模型自由回答，容易出现无依据判断、幻觉引用、遗漏隐患和过度自信等问题。

FireAgent 的核心目标是把“大模型能看图”升级为“系统能基于证据做安全判断”：

- **Evidence-first**：输出风险结论前必须先召回规则证据。
- **Safety-aware**：证据不足时触发开放集守护，避免强行下结论。
- **Scene-grounded**：根据校园、住宅、施工、工业等场景动态路由规则。
- **Traceable**：保留查询、候选规则、阈值、守护状态和历史记录。
- **Deployable**：提供 Web 页面、微信小程序端和 FastAPI 后端原型。

## Core Capabilities

| Capability | Description |
| --- | --- |
| Multimodal inspection | Upload a fire-safety scene image and extract visual facts. |
| Evidence-grounded reasoning | Retrieve fire-safety rules before producing risk conclusions. |
| Scene-aware retrieval | Route queries by campus, residential, industrial and construction contexts. |
| Conservative refusal | Refuse or ask for human review when evidence is weak. |
| Memory and governance | Track historical cases, recurring hazards, open tasks and risk trends. |
| Debuggable pipeline | Return retrieval queries, evidence IDs, guardrail decisions and latency fields. |

## Method Highlights

### 1. Two-Hop Evidence-Constrained Inference

系统将图片分析拆成两个阶段：

```text
Stage 1: Visual Fact Extraction
Y1 = g_vlm(I, s, u) = {o, h, k, r_h}

Stage 2: Evidence-Constrained Reasoning
Y2 = g_llm(Y1, E) = {r, Z, A}
```

- `Y1` 只负责抽取现场事实、候选隐患和检索关键词。
- `E` 来自消防规则知识库和检索增强模块。
- `Y2` 基于证据生成风险等级、隐患结论和整改建议。

这种设计将“看到了什么”和“是否构成隐患”解耦，降低多模态模型的自由发挥空间。

### 2. Scene-Aware Hybrid RAG

FireAgent 使用面向消防规则的混合检索策略，融合关键词匹配、向量相似度、Dense 双塔语义索引和场景化加权：

```text
S_base(d,q) = alpha * S_lex + beta * S_vec + gamma * S_dense
S(d,q) = S_base + b_scene + b_path + b_hint
```

检索查询由三类路径组成：

- **主查询**：由图片观察事实和关键词生成。
- **场景查询**：由宿舍、楼道、工业、施工等场景模板生成。
- **隐患查询**：由电气、堵塞、烟火、疏散等隐患类型生成。

### 3. Evidence Tree Retrieval

为了避免单一查询漏召回，系统将检索过程建模为证据树：

```text
Score_tree(d) = sum_{p in P(d)} w_p * s_p(d)
```

同一条规则如果被主查询、场景查询和隐患查询多路径命中，会获得更高可信度。证据树让规则召回从“单点关键词命中”变成“多视角证据汇聚”。

### 4. Submodular Evidence Set Selection

最终证据不是简单取 Top-k，而是选择一组互补证据：

```text
Delta(d | E)
  = w_R  * R(d)
  + w_N  * novelty(d, E)
  + w_sD * source_diversity(d, E)
  + w_hD * hazard_coverage(d, E)
```

该目标同时考虑相关性、新颖性、来源多样性和隐患覆盖，避免多条相似法规重复占据证据列表。

### 5. Dynamic Retrieval Budget

复杂图片需要更多规则证据，简单图片不应引入过多噪声。FireAgent 根据查询长度、隐患数量、工业场景和冲突线索估计检索预算：

```text
C(q) = lambda_1 * len(q)
     + lambda_2 * |h|
     + lambda_3 * I(scene = industrial)
     + lambda_4 * conflict(h)

K(q) = K_min + eta * sigmoid(C(q))
```

### 6. Open-Set Guardrail

消防安全场景中，“错误自信”比“不回答”更危险。系统在证据不足时触发保守策略：

```text
Guard(q) = I(n_cand < tau_n or s_top < tau_s or cover < tau_c)
```

守护机制从证据数量、最高证据分数和隐患覆盖度三个角度判断是否应该继续生成。

### 7. Four-Layer Memory

FireAgent 将巡检过程建模为持续治理任务，而不是一次性识别：

- **Core Memory**：系统级安全边界与输出规范。
- **Task Memory**：当前巡检任务目标、场景和状态。
- **Short-Term Memory**：会话内上下文、追问与工具调用轨迹。
- **Long-Term Memory**：历史案例、复发风险、整改任务和风险画像。

更多算法细节见 [docs/ALGORITHMS.md](docs/ALGORITHMS.md)。

## System Architecture

```mermaid
flowchart LR
    U["Web / WeChat Mini Program"] --> API["FastAPI Service"]
    API --> A["FireAgent Orchestrator"]
    A --> V["Stage1 VLM<br/>visual facts"]
    V --> Q["Query Builder<br/>main / scene / hazard"]
    Q --> R["Hybrid Retriever<br/>lexical + vector + dense"]
    R --> T["Evidence Tree<br/>path aggregation"]
    T --> S["Set Selection<br/>diversity + coverage"]
    S --> G["Open-Set Guardrail"]
    G --> L["Stage2 LLM<br/>evidence-constrained reasoning"]
    L --> DB["SQLite<br/>records / memory / cache"]
    DB --> U
```

## Repository Layout

```text
.
├── backend/                    # FastAPI backend and experiments
│   ├── app/
│   │   ├── api/                # REST APIs
│   │   ├── core/               # config, CORS, settings
│   │   ├── data/               # fire rules and scene playbooks
│   │   ├── db/                 # SQLAlchemy models and CRUD
│   │   └── services/           # analyzer, retriever, guardrail, memory
│   ├── eval_*.py               # retrieval / guardrail / baseline evaluation
│   └── requirements.txt
├── web/                        # static Web demo
├── pages/ utils/ app.*          # WeChat mini program entry
├── docs/                       # algorithm notes and technical documentation
```

## Experimental Snapshot

The project includes reproducible retrieval and guardrail evaluation scripts under `backend/`.

| Setting | Dataset | Top-1 | Top-3 | MRR |
| --- | --- | ---: | ---: | ---: |
| Dynamic retrieval | dev-650 | 0.5092 | 0.9123 | 0.7019 |
| Set selection | dev-650 | 0.5092 | 0.9000 | 0.7047 |
| Evidence tree | dev-650 | **0.5938** | 0.9015 | **0.7447** |
| Dynamic retrieval | blind-650 | 0.4554 | 0.8769 | 0.6555 |
| Set selection | blind-650 | 0.4554 | 0.8662 | 0.6560 |
| Evidence tree | blind-650 | **0.5338** | 0.8585 | **0.6899** |

Open-set guardrail evaluation:

| Guardrail | Samples | Refusal Precision | Refusal Recall | False Accept |
| --- | ---: | ---: | ---: | ---: |
| hybrid_local | 200 | 1.000 | 0.290 | 142 |
| strict_guardrail | 200 | **1.000** | **0.365** | **127** |

Interpretation:

- Evidence tree improves Top-1 by about **8.46 points** on the dev set and **7.84 points** on the blind set compared with dynamic retrieval.
- Guardrail precision is high, but refusal recall remains an important future-work direction.
- The benchmark focuses on rule retrieval and evidence grounding; the system is a research prototype rather than a certified fire-safety product.

## Quick Start

### Backend

```powershell
cd backend
pip install -r requirements.txt

# Optional: configure real multimodal / text model calls.
$env:SILICONFLOW_API_KEY="your_api_key"

uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

Useful endpoints:

- API docs: `http://127.0.0.1:8010/docs`
- Health check: `http://127.0.0.1:8010/health`
- Web demo mounted by backend: `http://127.0.0.1:8010/web/`

### Web Frontend

The static frontend lives in `web/` and uses `http://127.0.0.1:8010` as the default backend.

```powershell
# Option 1: served by FastAPI after backend startup
http://127.0.0.1:8010/web/

# Option 2: standalone static server
python -m http.server 5500
http://127.0.0.1:5500/web/index.html
```

### WeChat Mini Program

Open the repository root in WeChat DevTools. The mini program entry files are:

- `app.js`
- `app.json`
- `pages/`
- `utils/`

Set `utils/config.js` to the reachable backend address, for example `http://127.0.0.1:8010` or a LAN IP address during device debugging.

## Core APIs

All versioned APIs are under `/api/v1`.

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/analysis/upload` | Upload an image and run two-hop analysis |
| `GET` | `/records` | Query historical analysis records |
| `GET` | `/records/{record_id}` | Get one analysis detail |
| `GET` | `/records/insights` | Aggregate recent risk trends |
| `POST` | `/agent/chat` | Chat with the safety inspection agent |
| `GET` | `/memory/snapshot` | Export four-layer memory snapshot |
| `GET` | `/scene-guides` | Get scene-specific inspection guidance |

## Evaluation Scripts

Representative scripts:

```powershell
cd backend

# Retrieval ablation
python eval_ablation.py

# Open-set guardrail evaluation
python eval_open_set_guardrail.py

# Publication-style baselines
python eval_publication_baselines.py
python eval_publication_strong_baselines.py
```

## Disclaimer

FireAgent is a research prototype. Its outputs should be treated as auxiliary inspection suggestions, not as legally binding fire-safety certification or professional inspection conclusions.

## License

This project is open-sourced under the [MIT License](LICENSE).

FireAgent is a research prototype for multimodal fire-safety analysis. The MIT License covers the source code, while real-world fire-safety deployment still requires professional inspection, domain validation and local compliance review.
