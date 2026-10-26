# Architecture

## 1. System overview

![System architecture](diagrams/architecture.png)

Editable source: [`diagrams/architecture.html`](diagrams/architecture.html) (open it in a browser; add the official logos to `diagrams/logos/` as described in its README).

```mermaid
flowchart LR
    U[Student / browser] -->|HTTPS| FE[Angular 20 SPA<br/>Vercel]
    FE -->|REST + JWT · SSE| API[FastAPI backend + LangGraph agents<br/>Render · Docker]
    API -->|validate JWT| SA[(Supabase Auth)]
    API -->|SQL / RPC · LangGraph checkpoints| DB[(Supabase Postgres<br/>+ pgvector)]
    API -->|chat + embeddings<br/>Cloudflare Tunnel| OL[Ollama on a team machine<br/>qwen2.5:7b · nomic-embed-text]
    YF[Yahoo Finance · yfinance<br/>one-time ingestion] -->|historical_data| DB
    API -.->|optional traces| LF[Langfuse<br/>self-hosted]
```

## 2. Backend layers

```
app/
  main.py          FastAPI app, CORS, routers
  core/            config, Supabase clients, auth dependency (get_current_user)
  modules/         one package per feature: routes -> service -> (schema)   [controllers]
  agents/          LangGraph graphs: explain, chat, insights, compare, report, setup, what-if, knowledge (RAG)
  vectorstore/     embeddings + pgvector repository
  services/        pure computation: indicators, strategies, benchmark, historical data
```

Rule of dependencies: `routes -> service -> agents / vectorstore / services -> Supabase`. Routes never touch the database directly.

## 3. Document ingestion pipeline (US-33)

```mermaid
flowchart LR
    A[Upload<br/>POST /documents] --> B[Validate<br/>type, size, name]
    B --> C[Extract text<br/>PDF / DOCX / CSV / TXT / MD]
    C --> D[Chunk<br/>800 chars, 120 overlap]
    D --> E[Embed<br/>nomic-embed-text, 768 dims]
    E --> F[(documents +<br/>document_chunks<br/>pgvector)]
    F --> G[Confirm<br/>status = ready]
```

A document row is created first as `processing`; any failure leaves it as `failed` with the reason, so nothing is half-indexed silently.

## 4. Knowledge agent graph (US-30, LangGraph)

```mermaid
flowchart TD
    S([START]) --> V[validate_intent]
    V -->|question| R[retrieve<br/>embed + pgvector search]
    V -->|greeting / invalid| H[save_history]
    R --> G{grade<br/>enough information?}
    G -->|yes| GEN[generate<br/>answer only from context<br/>+ cite sources]
    G -->|no| REF[refuse<br/>fixed refusal text]
    GEN --> H
    REF --> H
    H --> E([END])
```

### Hallucination control

| # | Strategy | Where |
|---|----------|-------|
| 1 | Minimum similarity threshold when retrieving | `retrieve` (`RETRIEVAL_THRESHOLD`) |
| 2 | Dedicated sufficiency node: similarity floor + LLM yes/no check | `grade` |
| 3 | Prompt restricted to the retrieved context | `ANSWER_SYSTEM_PROMPT` |
| 4 | Explicit refusal with a fixed text (also when the model itself reports insufficient context) | `refuse`, `generate` |
| 5 | Sources shown with every answer (file, page, snippet) | `generate` |

## 5. Simulation agents

The 8 LangGraph graphs (explain, chat, insights, compare, report, setup, what-if and knowledge), with one diagram per agent showing its nodes, edges and the tools each node uses, are described in **[agents.md](agents.md)**.

![How the agents work](agents/diagrams/overview.png)
