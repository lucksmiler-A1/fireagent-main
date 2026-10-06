# FireAgent Algorithms

This document summarizes the algorithmic core of FireAgent: a knowledge-enhanced multimodal agent for fire-safety hazard image analysis.

## 1. End-to-End Pipeline

```text
Input image
  -> Stage1 visual fact extraction
  -> query construction
  -> hybrid retrieval
  -> evidence tree aggregation
  -> evidence set selection
  -> open-set guardrail
  -> Stage2 evidence-constrained reasoning
  -> memory update and record storage
```

The central design principle is **evidence before conclusion**. The system should not produce a high-confidence fire-safety judgment unless the retrieved rule evidence is sufficient.

## 2. Two-Hop Inference

### Stage1: Visual Fact Extraction

```text
Y1 = g_vlm(I, s, u) = {o, h, k, r_h}
```

Where:

- `I`: input image.
- `s`: selected or inferred scene.
- `u`: optional user hint.
- `o`: visual observations.
- `h`: candidate hazard tags.
- `k`: retrieval keywords.
- `r_h`: preliminary risk hint.

Stage1 avoids final compliance judgment. Its job is to translate an image into structured facts that can drive retrieval.

Example:

```text
Image: open electrical cabinet, exposed cables, cartons nearby
o: cabinet open, cables visible, combustible materials nearby
h: electrical fire risk, combustible stacking, equipment exposure
k: electrical cabinet, cables, combustible materials, fire hazard
```

### Stage2: Evidence-Constrained Reasoning

```text
Y2 = g_llm(Y1, E) = {r, Z, A}
```

Where:

- `E`: selected evidence rules.
- `r`: risk level.
- `Z`: hazard conclusions.
- `A`: corrective actions.

Stage2 uses `Y1` and `E` together. It should cite evidence, identify the hazard and produce actionable recommendations.

## 3. Query Construction

FireAgent builds multiple query paths rather than one flat query:

```text
q_main  = Compose(o, k)
q_scene = TemplateScene(s)
Q_haz   = {TemplateHazard(t) for t in h}
```

Path types:

- **Main path**: key objects and states observed in the image.
- **Scene path**: campus, residential, construction, industrial and similar scenarios.
- **Hazard path**: electrical, blocked evacuation, smoke/fire, extinguisher, combustible storage and other hazard categories.

This makes retrieval robust when a single keyword formulation misses relevant rules.

## 4. Hybrid Retrieval Score

For each candidate rule `d` and query `q`, FireAgent combines lexical, vector and dense semantic scores:

```text
S_base(d,q) = alpha * S_lex(d,q)
            + beta  * S_vec(d,q)
            + gamma * S_dense(d,q)
```

Then it adds domain-aware bonuses:

```text
S(d,q) = S_base(d,q) + b_scene + b_path + b_hint
```

Meaning:

- `S_lex`: lexical or keyword-level match.
- `S_vec`: TF-IDF or sparse vector similarity.
- `S_dense`: dense semantic similarity from a two-tower embedding model.
- `b_scene`: bonus when the rule matches the current scene.
- `b_path`: bonus from multi-path evidence hits.
- `b_hint`: bonus when a rule matches inferred hazard hints.

Dense retrieval is used to capture synonym and paraphrase relationships, for example:

```text
"电线裸露" ~= "导线外露" ~= "线路未采取保护措施"
```

## 5. Evidence Tree Retrieval

Evidence tree retrieval aggregates scores from multiple query paths:

```text
Score_tree(d) = sum_{p in P(d)} w_p * s_p(d)
```

Where:

- `P(d)`: paths that retrieved rule `d`.
- `w_p`: path weight.
- `s_p(d)`: rule score on path `p`.

Intuition:

- A rule hit only by one weak keyword may be accidental.
- A rule hit by main path, scene path and hazard path is more likely to be relevant.

Compared with ordinary multi-query retrieval, the evidence tree has three domain adaptations:

- Sub-questions come from structured scene and hazard priors, not from unconstrained chain-of-thought expansion.
- Path weights are not uniform; the main path remains dominant to avoid noisy branches diluting ranking.
- Path-hit benefit is coordinated with the hybrid retrieval score to avoid over-promoting low-relevance rules.

## 6. Submodular Evidence Set Selection

Top-k retrieval may select many near-duplicate rules. FireAgent instead optimizes a set-level objective:

```text
max_{|E| = k} sum_{d in E} (
    w_R  * R(d)
  + w_N  * N(d,E)
  + w_sD * D_s(d,E)
  + w_hD * D_h(d,E)
)
```

Where:

- `R(d)`: relevance of rule `d`.
- `N(d,E)`: novelty compared with already selected evidence.
- `D_s(d,E)`: source diversity.
- `D_h(d,E)`: hazard coverage diversity.

The greedy marginal gain form is:

```text
Delta(d | E)
  = w_R  * R(d)
  + w_N  * max_{e in E}(1 - cos(d,e))
  + w_sD * I(source(d) not in Sources(E))
  + w_hD * |HazardCover(d) \ HazardCover(E)|
```

Pseudo-code:

```text
E <- empty set

while |E| < k and C is not empty:
    d* <- argmax_{d in C} Delta(d | E)

    if Delta(d* | E) <= epsilon:
        break

    E <- E union {d*}
    C <- C \ {d*}

return E
```

Engineering adjustments:

- Add explicit hazard coverage so that each major hazard has rule support.
- Use a marginal-gain threshold `epsilon` to avoid adding weak evidence just to fill `k`.
- Normalize source distribution so that a large standard does not dominate only because it contains more clauses.

A simple source normalization expression is:

```text
D_s_norm(d,E) = D_s(d,E) / log(1 + N_source)
```

Where `N_source` is the number of rules from the same source as `d`.

## 7. Dynamic Retrieval Budget

Different images need different retrieval depth. FireAgent estimates query complexity:

```text
C(q) = lambda_1 * len(q)
     + lambda_2 * |h|
     + lambda_3 * I(scene = industrial)
     + lambda_4 * conflict(h)
```

Then maps complexity to a retrieval budget:

```text
K(q) = K_min + eta * sigmoid(C(q))
```

Interpretation:

- Short query, few hazards, simple scene -> small budget.
- Long query, multiple hazards, industrial or conflicting clues -> larger budget.

This keeps the system efficient on simple cases and more careful on complex cases.

## 8. Open-Set Guardrail

The guardrail determines whether FireAgent should continue to Stage2 generation:

```text
Guard(q) = I(n_cand < tau_n or s_top < tau_s or cover < tau_c)
```

Where:

- `n_cand`: number of candidate evidence rules.
- `s_top`: top evidence relevance score.
- `cover`: hazard coverage ratio.
- `tau_n`, `tau_s`, `tau_c`: thresholds.

If any condition is triggered, the system returns a conservative response, such as:

```text
Evidence is insufficient. Please provide a clearer image or request human review.
```

This is important because fire-safety systems should prefer conservative uncertainty over unsupported confidence.

## 9. Four-Layer Memory

FireAgent uses four memory layers:

```text
Core Memory
  -> safety rules, output policy, system boundaries

Task Memory
  -> current inspection goal, active scene and status

Short-Term Memory
  -> current dialogue context and recent tool calls

Long-Term Memory
  -> historical cases, recurring hazards, task follow-ups
```

The memory router provides relevant context to the planner and reasoning modules. It supports multi-turn inspection questions such as:

```text
"刚才那张图还有哪些隐患？"
"最近一周哪类风险最多？"
"这个整改任务是否重复出现？"
```

## 10. Planner and Tool Routing

The planner decides which capabilities are needed:

```text
intent <- parse user request

if image is provided:
    call analyzer

if rules are needed:
    call retriever

if history is needed:
    query records and long-term memory

if evidence is weak:
    call guardrail

return structured response
```

This keeps the agent modular. Image analysis, retrieval, memory, records and advice generation can evolve independently.

## 11. Algorithm Relationship

```text
Algorithms 1-2:
  Make multimodal reasoning stepwise and evidence-constrained.

Algorithms 3-4:
  Retrieve the right fire-safety rules through hybrid scoring and evidence tree aggregation.

Algorithms 5-6:
  Select a compact, diverse and complexity-aware evidence set.

Algorithm 7:
  Prevent unsupported conclusions in open-set or weak-evidence cases.

Algorithms 8-9:
  Support multi-turn interaction, historical governance and tool routing.
```

## 12. Practical Example

Input:

```text
Open electrical cabinet, messy cables, cartons nearby.
```

Processing:

```text
Stage1:
  observations = cabinet open, exposed cables, combustible materials nearby
  hazards = electrical fire risk, combustible stacking
  keywords = electrical cabinet, cables, combustible, fire risk

RAG:
  q_main = electrical cabinet + exposed cable + carton
  q_scene = indoor electrical equipment safety
  q_hazard = electrical fire + combustible storage

Evidence tree:
  boost rules hit by multiple query paths

Set selection:
  choose rules covering electrical risk and combustible storage

Guardrail:
  continue only if evidence quantity, top score and hazard coverage are sufficient

Stage2:
  output risk level, hazard explanation, cited evidence and corrective actions
```

Output:

```text
Risk: medium-high
Hazards: electrical fire risk; combustible material near electrical equipment
Actions: close cabinet door; organize wiring; remove cartons; request manual inspection if needed
```
