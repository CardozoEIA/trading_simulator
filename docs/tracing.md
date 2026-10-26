# Tracing the agents with Langfuse (optional)

Tracing shows the **real flow** of each request: which graph nodes ran, every model call with its prompt and answer, every tool call with its input and output, and how long each step took. It complements the static diagrams in [agents.md](agents.md).

Tracing is **optional**. With no Langfuse keys the backend behaves exactly as without it: the `langfuse` package is not even imported and no network call is made. The tests never contact Langfuse (`tests/conftest.py` clears the keys).

## How it works

- `backend/app/agents/common/tracing.py`
  - `tracing_config(name, user_id, session_id, base)` adds the Langfuse LangChain callback, the run name and the metadata (user, session, tag) to the LangGraph config of a run. Without keys it returns `base` unchanged. It never raises.
  - `child_config(config, ...)` is used by nodes that run another graph (chat → explain, chat → compare, what-if → compare), so the inner graph appears **inside** the parent trace. Only the Langfuse handler is passed down, never the chat's token streaming, so an inner model's raw output is not streamed to the student.
  - `flush_tracing()` is called when the backend stops (FastAPI lifespan), so traces of background tasks such as the insights are not lost.
- Every agent entry point passes its config:

| Trace name | Started by | Session |
|---|---|---|
| `explain` | Explain button (`modules/agent/service.py`) | simulation id |
| `chat` | Guided mode question, normal and streaming (`modules/chat/service.py`) | `simulation_id:user_id` (the chat thread) |
| `insights` | Simulation finished, background task (`modules/insights/service.py`) | simulation id |
| `compare` | Compare in History (`modules/compare/service.py`) | first simulation id |
| `report` | Generate report (`modules/report/service.py`) | simulation id |
| `setup` | Describe your simulation (`modules/setup/service.py`) | — |
| `what-if` | Run what-if (`modules/whatif/service.py`) | simulation id |
| `knowledge` | Knowledge question (`modules/knowledge/service.py`) | `knowledge:user_id` |

Only ids and the trace name are sent as metadata: never the JWT, passwords or Supabase keys. Prompts and answers of the model **are** sent (that is the point of a trace), which is why a self-hosted Langfuse is recommended.

## 1. Run Langfuse

**Self-hosted (recommended: every prompt and answer stays on your machine).** Only Langfuse's `docker-compose.yml` is needed (the images are pre-built). A full `git clone` fails on Windows because some paths are too long, so download just that file:

```bash
mkdir langfuse && cd langfuse
curl -L -o docker-compose.yml https://raw.githubusercontent.com/langfuse/langfuse/main/docker-compose.yml
docker compose up -d
```

Open <http://localhost:3000>, create an account, an organization and a project, and copy the project's **public** and **secret** keys. Langfuse uses ports 3000, 5432 (Postgres) and 9090, among others; stop any other container using them first.

To skip the sign-up, put a `.env` next to the compose file before `docker compose up -d`; Langfuse then creates the user, the project and its keys on the first start:

```env
LANGFUSE_INIT_ORG_ID=market-navigator
LANGFUSE_INIT_ORG_NAME=Market Navigator AI
LANGFUSE_INIT_PROJECT_ID=market-navigator
LANGFUSE_INIT_PROJECT_NAME=market-navigator
LANGFUSE_INIT_PROJECT_PUBLIC_KEY=pk-lf-<random>
LANGFUSE_INIT_PROJECT_SECRET_KEY=sk-lf-<random>
LANGFUSE_INIT_USER_EMAIL=admin@market-navigator.local
LANGFUSE_INIT_USER_NAME=Admin
LANGFUSE_INIT_USER_PASSWORD=<choose one>
```

**Langfuse Cloud** (free tier) also works: create a project at <https://cloud.langfuse.com> and use `LANGFUSE_BASE_URL=https://cloud.langfuse.com`. Prompts and answers are then stored on Langfuse's servers.

## 2. Connect the backend

Add the keys to `backend/.env` (see `.env.example`) and restart the backend:

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=http://localhost:3000
```

Both keys are needed; with only one, tracing stays off. If Langfuse is not reachable the app keeps working: the SDK logs that it could not export the spans and the requests are not affected.

### Troubleshooting

- **Memory.** Langfuse (about 2 GB in Docker) and `qwen2.5:7b` (about 5 GB) together need more than 8 GB free. If Ollama fails with `unable to allocate ... buffer`, close other programs or stop Langfuse while not tracing (`docker compose stop` in its folder).
- **Nothing in the trace list.** Check that both keys are set and the backend was restarted. Langfuse v4 runs in *events only* mode: the old `GET /api/public/traces` endpoint returns 404 there, but the UI and `GET /api/public/v2/observations` show the traces.
- **`langchain` is required.** Langfuse's LangChain integration imports the `langchain` package (pinned in `requirements.txt`); without it tracing turns itself off and logs a warning.

## 3. What to look at

Use the app, then open **Tracing → Traces** in Langfuse and filter by name (tag) or by user.

- **Run tree**: e.g. a chat question about a day shows `chat` → `supervisor` → `explain_agent` → `agent` → `tools` → `agent`.
- **Tool calls**: each tool's input (e.g. the date) and output (the recorded price, decision or indicators).
- **Model calls**: the exact prompt (system + facts) and the answer, including the JSON of the router and of the agents that verify their text; a retry shows up as a second `explain` / `write` step after `verify`.
- **Latency** per node and per model call, to see where the time goes.
- **Sessions**: all turns of one chat thread grouped together.

## 4. Evidence for the presentation

| Trace | How to produce it | Screenshot |
|---|---|---|
| Chat → explain | Guided mode: "Why did it buy on day 12?" (router → explain → tool calls) | `docs/screenshots/trace-chat-explain.png` |
| Compare | History: select two runs → Compare (parallel fetch → diff → explain → verify) | `docs/screenshots/trace-compare.png` |
| What-if | Guided mode: "What if the stop-loss were 3%?" → Run what-if (load → copy → run → compare) | `docs/screenshots/trace-whatif.png` |
| Knowledge refusal | Knowledge: a question outside the documents (retrieve → grade → refuse) | `docs/screenshots/trace-knowledge-refusal.png` |

![Chat → explain trace](screenshots/trace-chat-explain.png)

![Compare trace](screenshots/trace-compare.png)

![What-if trace](screenshots/trace-whatif.png)

![Knowledge refusal trace](screenshots/trace-knowledge-refusal.png)
