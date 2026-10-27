# How the agents work

Market Navigator AI has **8 LangGraph graphs**, all in `backend/app/agents/<name>/graph.py`. They share one local model (`agents/common/llm.py`: Ollama `qwen2.5:7b`, temperature 0, 60 s timeout); the knowledge agent also uses `nomic-embed-text` for embeddings.

The diagrams below are drawn by hand from the graphs exported from the code (`docs/agents/graphs/*.mmd`, see [How to regenerate](#4-how-to-regenerate)). If a diagram and the code disagree, the code is right.

| Agent | Story | Flow | Started by |
|---|---|---|---|
| [explain](#explain-us-20) | US-20, US-31 | `agent ⇄ tools → verify` (ReAct + self-check) | Explain button, chat `explain_agent` |
| [chat](#chat-us-2225) | US-22/25 | `supervisor` → one route | Question in guided mode |
| [insights](#insights-us-26) | US-26 | `gather_facts → explain → verify` | A simulation finishes |
| [compare](#compare-us-27) | US-27 | `fetch_a ∥ fetch_b → diff → explain → verify` | Compare in History, chat, what-if |
| [report](#report-us-32) | US-32 | `gather_facts → write → verify` | Generate report |
| [setup](#setup-us-29) | US-29 | `extract → validate → ask_missing \| propose` | Describe your simulation |
| [what-if](#what-if-us-28) | US-28 | `load → copy → run → compare \| fallback` | Run what-if (after confirming) |
| [knowledge](#knowledge-us-30) | US-30 | `validate_intent → retrieve → grade → generate \| refuse → save_history` | Knowledge question |

---

## 1. Overview

Each entry point starts one graph. Some graphs reuse others, and two steps wait for the student before anything runs or is saved.

```mermaid
flowchart TB
    T1(["Explain button"]) --> EXP
    T2(["Simulation finishes"]) --> INS
    T3(["Chat question"]) --> SUP
    T4(["Compare in History"]) --> CMP
    T5(["Generate report"]) --> REP
    T6(["Describe a simulation"]) --> SET
    T7(["Knowledge question"]) --> KNO

    EXP["<b>explain</b><br/>agent ⇄ tools → verify<br/>(ReAct + self-check)"]
    INS["<b>insights</b><br/>gather_facts → explain → verify"]
    SUP{"<b>chat supervisor</b><br/>router → JSON route"}
    CMP["<b>compare</b><br/>fetch_a ∥ fetch_b → diff<br/>→ explain → verify"]
    REP["<b>report</b><br/>gather_facts → write → verify"]
    SET["<b>setup</b><br/>extract → validate<br/>→ ask_missing | propose"]
    KNO["<b>knowledge (RAG)</b><br/>validate_intent → retrieve → grade<br/>→ generate | refuse → save_history"]

    SUP -->|a specific day| EXP
    SUP -->|overview| SUM["insights_agent<br/>highlights summary"]
    SUP -->|vs buy &amp; hold| ANS["answer"]
    SUP -->|what is X?| CON["conceptual_agent<br/>glossary + memory"]
    SUP -->|compare runs| CMP
    SUP -->|try another risk limit| PROP["propose_change<br/>proposal + plan"]
    SUP -->|"off-topic · unclear"| FIX["off_topic · clarify<br/>fixed reply"]

    PROP --> H1{{"Student presses<br/>Run what-if"}}
    H1 --> WI["<b>what-if</b><br/>load → copy → run<br/>→ compare | fallback"]
    WI -->|original vs copy| CMP
    SET --> H2{{"Student presses<br/>Use these values"}}
    H2 --> FORM["Normal setup steps<br/>config → risk → confirm"]

    classDef trigger fill:#13233a,stroke:#13233a,color:#ffffff
    classDef subflow fill:#e4ecf8,stroke:#2f63ad,stroke-width:2px,color:#13233a
    classDef human fill:#fbf6ec,stroke:#c9a15c,color:#13233a
    class T1,T2,T3,T4,T5,T6,T7 trigger
    class EXP,INS,CMP,REP,SET,KNO,WI subflow
    class H1,H2 human
```

---

## 2. One diagram per agent

Solid arrows are the graph edges; dashed lines connect a node to the tools and data it uses. Conditional edges carry their condition as the label.

| Shape | Meaning |
|---|---|
| Dark pill | `START` / `END` |
| Blue box | Graph node |
| Dashed gold box | Tool or helper the node calls |
| Cream cylinder | Data read or written |
| Double-border box | Another agent graph run inside the node |

### explain (US-20, US-31)

Image: [`agents/graphs/explain.png`](agents/graphs/explain.png)

ReAct loop: the model decides which tools to call, LangGraph runs them and gives the results back, until the model answers without tool calls. That draft then goes through a **verify** node (US-31): every sentence is checked and the ones with a date or number that no tool returned (or that promise future results) are removed, with a note for the student. The check is code, not the model grading itself. Builder: `build_agent_graph(simulation_id, user_id)`; the tools are bound to that simulation.

What the student can see (explanation modal and chat): the **trace** — every tool called, its arguments and the value it returned — and the **verification** result. Both are stored in `agent_traces` and readable at `GET /simulations/{id}/traces`.

```mermaid
flowchart LR
    S([START]) --> A[agent<br/>qwen2.5:7b + tools]
    A -->|tool calls| T[tools]
    T --> A
    A -->|no tool calls| V[verify<br/>drop unbacked sentences]
    V --> E([END])

    T -.- t1[get_price] & t3[get_indicators] & t5[get_market_regime] -.- d1[(simulation_signals)]
    T -.- t2[get_decision] & t6[get_ensemble_breakdown] -.- d2[(simulation_decisions)]
    T -.- t4[get_risk_config] -.- d3[(simulations +<br/>risk_configurations)]

    classDef io fill:#13233a,stroke:#13233a,color:#ffffff
    classDef tool fill:#ffffff,stroke:#c9a15c,stroke-dasharray:4 3,color:#13233a
    classDef data fill:#fbf6ec,stroke:#c9a15c,color:#13233a
    classDef subflow fill:#e4ecf8,stroke:#2f63ad,stroke-width:2px,color:#13233a
    class S,E io
    class t1,t2,t3,t4,t5,t6 tool
    class d1,d2,d3 data
```

### chat (US-22/25)

Image: [`agents/graphs/chat.png`](agents/graphs/chat.png)

The `supervisor` asks the router model for a route as JSON (`routing/router.py`); Python validates it and resolves dates, risk proposals and the simulation to compare with. `propose_change`, `off_topic` and `clarify` answer directly from the supervisor and end the turn; `off_topic` and `clarify` always use fixed text, never the router's own wording.

```mermaid
flowchart TB
    S([START]) --> SUP[supervisor<br/>router model → JSON route]
    SUP -.- h[injection check · resolve_date<br/>build_proposal + plan · resolve_comparison]
    SUP -->|explain_agent| EA[explain_agent]
    SUP -->|insights_agent| IA[insights_agent]
    SUP -->|answer| AN[answer]
    SUP -->|conceptual| CA[conceptual_agent]
    SUP -->|compare| CO[compare_agent]
    SUP -->|"propose_change · off_topic · clarify<br/>reply from the supervisor"| E([END])

    EA -.- g1[[explain graph]]
    IA -.- t1[summarize_simulation]
    AN -.- t2[buy_and_hold_comparison]
    CA -.- t3[glossary topics only<br/>+ relevant earlier turns]
    CO -.- g2[[compare graph<br/>compare_simulations_text]]
    g1 ~~~ E
    t1 ~~~ E
    t2 ~~~ E
    t3 ~~~ E
    g2 ~~~ E
    EA & IA & AN & CA & CO --> E

    classDef io fill:#13233a,stroke:#13233a,color:#ffffff
    classDef tool fill:#ffffff,stroke:#c9a15c,stroke-dasharray:4 3,color:#13233a
    classDef subflow fill:#e4ecf8,stroke:#2f63ad,stroke-width:2px,color:#13233a
    class S,E io
    class h,t1,t2,t3 tool
    class g1,g2 subflow
```

The conversation is stored by a Postgres checkpointer (`modules/chat/checkpointer.py`, in-memory if `SUPABASE_DB_URL` is not set) and in `chat_messages`; `conceptual_agent` only sees the earlier turns relevant to the new question (`modules/chat/memory.py`). `propose_change` returns the proposal and its plan; it never changes anything (see what-if).

### insights (US-26)

Image: [`agents/graphs/insights.png`](agents/graphs/insights.png)

Started by the backend, not by a question, when a simulation reaches `FINISHED` or `STOPPED_BY_RISK`. The highlights are computed by code; the model only explains each one.

```mermaid
flowchart LR
    S([START]) --> G[gather_facts]
    G -->|no highlights| E([END])
    G -->|highlights| X[explain<br/>one text per highlight]
    X --> V[verify]
    V -->|values not in the facts,<br/>attempts left| X
    V -->|all backed or<br/>no attempts left| E

    G -.- t1[get_run_overview] & t2[find_highlights] -.- d[(simulation, trades,<br/>equity curve, signals)]
    V -.- u[unverified_values]

    classDef io fill:#13233a,stroke:#13233a,color:#ffffff
    classDef tool fill:#ffffff,stroke:#c9a15c,stroke-dasharray:4 3,color:#13233a
    classDef data fill:#fbf6ec,stroke:#c9a15c,color:#13233a
    classDef subflow fill:#e4ecf8,stroke:#2f63ad,stroke-width:2px,color:#13233a
    class S,E io
    class t1,t2,u tool
    class d data
```

`modules/insights/service.py` stores the verified texts in `simulation_insights`.

### compare (US-27)

Image: [`agents/graphs/compare.png`](agents/graphs/compare.png)

Both simulations are fetched in parallel through tools bound to the student. Only a slice of each run is read, never its daily data.

```mermaid
flowchart LR
    S([START]) --> A[fetch_a] & B[fetch_b]
    A & B --> D[diff<br/>pure Python]
    D --> X[explain<br/>likely drivers]
    X --> V[verify]
    V -->|rejected, attempts left| X
    V -->|verified or<br/>no attempts left| E([END])

    A & B -.- t[simulation_slice<br/>ownership check] -.- d[("configuration, metrics,<br/>buy &amp; hold, highlights")]
    V -.- u[unverified_values · wrong_directions<br/>makes_promises]

    classDef io fill:#13233a,stroke:#13233a,color:#ffffff
    classDef tool fill:#ffffff,stroke:#c9a15c,stroke-dasharray:4 3,color:#13233a
    classDef data fill:#fbf6ec,stroke:#c9a15c,color:#13233a
    classDef subflow fill:#e4ecf8,stroke:#2f63ad,stroke-width:2px,color:#13233a
    class S,E io
    class t,u tool
    class d data
```

`diff` computes the configuration differences, the metric deltas, which run is better in each metric and the winner by total return. `verify` also rejects text that names the wrong run as the larger or smaller one. The `list_simulations` tool is used by the chat supervisor to resolve "my previous one".

### report (US-32)

Image: [`agents/graphs/report.png`](agents/graphs/report.png)

```mermaid
flowchart LR
    S([START]) --> G[gather_facts<br/>fixed sections]
    G --> W[write<br/>narrative per section]
    W --> V[verify]
    V -->|rejected, attempts left| W
    V -->|done| E([END])

    G -.- t[load_report_data] -.- d[(configuration, results,<br/>metrics, trades, highlights)]
    V -.- u[unverified_values · makes_promises]

    classDef io fill:#13233a,stroke:#13233a,color:#ffffff
    classDef tool fill:#ffffff,stroke:#c9a15c,stroke-dasharray:4 3,color:#13233a
    classDef data fill:#fbf6ec,stroke:#c9a15c,color:#13233a
    classDef subflow fill:#e4ecf8,stroke:#2f63ad,stroke-width:2px,color:#13233a
    class S,E io
    class t,u tool
    class d data
```

The tables, figures and the disclaimer are written by code (`agents/report/facts.py`, `render.py`); a narrative that fails twice is dropped and the section keeps only its figures.

### setup (US-29)

Image: [`agents/graphs/setup.png`](agents/graphs/setup.png)

```mermaid
flowchart LR
    S([START]) --> X[extract<br/>model → JSON fields]
    X --> V[validate]
    V -->|missing or invalid fields| AM[ask_missing]
    V -->|complete| P[propose]
    AM & P --> E([END])

    V -.- c[coerce<br/>drop values not in the text]
    V -.- r[validate_configuration<br/>+ risk rules, read only]

    classDef io fill:#13233a,stroke:#13233a,color:#ffffff
    classDef tool fill:#ffffff,stroke:#c9a15c,stroke-dasharray:4 3,color:#13233a
    classDef data fill:#fbf6ec,stroke:#c9a15c,color:#13233a
    classDef subflow fill:#e4ecf8,stroke:#2f63ad,stroke-width:2px,color:#13233a
    class S,E io
    class c,r tool
```

`ask_missing` and `propose` are written by code. Nothing is saved: the proposal only pre-fills the normal setup form.

### what-if (US-28)

Image: [`agents/graphs/whatif.png`](agents/graphs/whatif.png)

Runs only through `POST /simulations/{id}/what-if`, i.e. after the student pressed **Run what-if** on the chat proposal.

```mermaid
flowchart LR
    S([START]) --> L[load]
    L --> C[copy]
    C --> R[run]
    R -->|finished in time| CM[compare]
    R -->|failed or too slow| F[fallback]
    CM & F --> E([END])

    L -.- l[ownership · original config<br/>build_proposal]
    C -.- c[(NEW configuration +<br/>risk configuration)]
    R -.- r[start_simulation<br/>90 s timeout]
    CM -.- g[[compare graph]]
    F -.- f[expected effect in words<br/>no numbers]

    classDef io fill:#13233a,stroke:#13233a,color:#ffffff
    classDef tool fill:#ffffff,stroke:#c9a15c,stroke-dasharray:4 3,color:#13233a
    classDef data fill:#fbf6ec,stroke:#c9a15c,color:#13233a
    classDef subflow fill:#e4ecf8,stroke:#2f63ad,stroke-width:2px,color:#13233a
    class S,E io
    class l,r,f tool
    class c data
    class g subflow
```

The original configuration, risk configuration and simulation are never updated. If the compare agent is unavailable, the computed comparison is returned without its explanation.

### knowledge (US-30)

Image: [`agents/graphs/knowledge.png`](agents/graphs/knowledge.png)

```mermaid
flowchart LR
    S([START]) --> VI[validate_intent]
    VI -->|question| RE[retrieve]
    VI -->|greeting / invalid| SH[save_history]
    RE --> GR[grade]
    GR -->|sufficient| GE[generate]
    GR -->|insufficient| RF[refuse]
    GE & RF --> SH
    SH --> E([END])

    RE -.- r[rewrite query · nomic-embed-text<br/>pgvector search] -.- d[(document_chunks)]
    GR -.- g[similarity floor + grader model]
    SH -.- h[(knowledge history)]

    classDef io fill:#13233a,stroke:#13233a,color:#ffffff
    classDef tool fill:#ffffff,stroke:#c9a15c,stroke-dasharray:4 3,color:#13233a
    classDef data fill:#fbf6ec,stroke:#c9a15c,color:#13233a
    classDef subflow fill:#e4ecf8,stroke:#2f63ad,stroke-width:2px,color:#13233a
    class S,E io
    class r,g tool
    class d,h data
```

`generate` answers only from the retrieved passages and cites them; `refuse` returns a fixed text.

---

## 3. Shared guarantees

- **On topic only.** Questions about anything other than trading, the student's simulations or the platform, and attempts to override the instructions, get a fixed reply: the chat routes them to `off_topic` (an injection check runs before any model call, and `conceptual` only answers questions about a glossary topic), the knowledge agent refuses them and the setup agent asks for a simulation description (`agents/common/scope.py`).
- **Own data only.** Every tool and service checks that the simulation or configuration belongs to the student (`user_id`); otherwise it is a 404.
- **Code computes, the model only writes.** Numbers, dates, differences and selections come from Python; the model turns them into plain language.
- **Verification.** `verify` rejects any number or date that is not in the facts (`agents/insights/verify.py`), comparisons the wrong way round (compare) and promises about future results; the model gets one retry, then the text is dropped.
- **Human in the loop.** Nothing is run or saved by an agent on its own: the what-if runs only after **Run what-if**, and a described setup only pre-fills the form the student then confirms.
- **Conversation memory.** Postgres checkpointer for the chat thread plus retrieval of the earlier turns relevant to the new question.
- **Graceful degradation.** If Ollama is down or slow the endpoint returns 503 with a clear message and the rest of the page keeps working.

---

## 4. How to regenerate

From `backend/`:

```bash
python -m scripts.export_agent_graphs
```

It builds every graph with a fake model and dummy settings (no Ollama, no Supabase, network blocked) and writes `docs/agents/graphs/<name>.mmd` with `graph.get_graph(xray=True).draw_mermaid()`. Compare those files with the diagrams above after changing a graph.

### PNGs for the presentation

Every diagram on this page, with its tools, is exported to `docs/agents/graphs/<name>.png`: `overview`, `explain`, `chat`, `insights`, `compare`, `report`, `setup`, `whatif` and `knowledge`. (The `.mmd` files next to them are the raw graphs exported from the code, without tools.)

After changing a diagram, export it again: paste the block into <https://mermaid.live> and use **Export → PNG**, or save it to a `.mmd` file and run `npx @mermaid-js/mermaid-cli -i <name>.mmd -o docs/agents/graphs/<name>.png`.

| Overview | Chat |
|---|---|
| ![Overview of the agents](agents/graphs/overview.png) | ![Chat agent](agents/graphs/chat.png) |
