# Market Navigator AI

Educational platform for trading decision support. Students run strategies on historical S&P 500 data, see why a position would be opened, held or rejected, and learn with an AI agent that **only answers from verified data and from the documents they upload**. No real money is ever involved.

## Features

- Backtesting engine with SMA, RSI, Bollinger Bands, Momentum and a regime-weighted ensemble, with a mandatory risk layer (stop-loss, position size, max drawdown).
- Results: metrics (Sharpe, drawdown, win rate, profit factor), equity curve, benchmark vs. buy & hold, full decision log.
- **AI agents (LangChain + LangGraph, local model through Ollama)**
  - *Explain*: tool-calling agent that explains a single decision from recorded data.
  - *Guided chat*: router + persistent memory, streaming answers, human-in-the-loop proposals.
  - *Insights*: key findings generated automatically when a simulation finishes.
  - ***Knowledge agent (RAG)***: upload your own documents (PDF, DOCX, TXT, MD, CSV); the agent answers only from them, cites its sources and refuses when it does not know.
- Authentication with Supabase Auth (JWT). Every endpoint except register and login requires a valid token.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the diagrams (system, ingestion pipeline, agent graph).

| Layer | Technology |
|-------|-----------|
| Frontend | Angular 20 (standalone components, signals) |
| Backend | FastAPI (Python 3.12) |
| Agents | LangChain, LangGraph |
| Local LLM | Ollama: `qwen2.5:7b` (chat, tools) and `nomic-embed-text` (embeddings) |
| Database + vector store | Supabase Postgres with pgvector |
| Auth | Supabase Auth (JWT) |

### Why these local models

- `qwen2.5:7b`: reliable tool calling and multilingual answers at a size that runs on a laptop with 8 GB of RAM. Limitation: noticeably slower and less obedient than hosted models, which is why the agent verifies its output (see *Hallucination control*).
- `nomic-embed-text`: small (274 MB) embedding model, 768 dimensions, good retrieval quality for its size.

## Run it locally

### Requirements
Python 3.12, Node 22, [Ollama](https://ollama.com), and a Supabase project.

### 1. Models
```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

### 2. Database
In the Supabase SQL editor run, in order, the files in `backend/migrations/` (`001_` ... `004_`).

### 3. Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example .env      # then fill in the values
uvicorn app.main:app --reload
```
API docs: http://localhost:8000/docs

### 4. Frontend
```powershell
cd frontend
npm ci
ng serve
```
App: http://localhost:4200

### Everything with Docker
```bash
cp .env.example backend/.env   # fill it in
docker compose up --build
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull nomic-embed-text
```

## Tests
```powershell
cd backend ; .\venv\Scripts\python -m pytest -q
cd frontend ; ng test --watch=false
```

## API (main endpoints)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/users/` | Register |
| POST | `/auth/login` | Log in, returns the JWT |
| GET | `/auth/me` | Current user |
| POST | `/documents` | Upload a document into the knowledge base |
| GET | `/documents` | List my documents |
| DELETE | `/documents/{id}` | Delete a document and its fragments |
| POST | `/knowledge/ask` | Ask the knowledge agent |
| GET / DELETE | `/knowledge/history` | Conversation history |
| POST | `/simulations/start` | Run a simulation |
| POST | `/simulations/{id}/chat/stream` | Guided chat (SSE) |

Full list: `/docs` (Swagger) once the backend is running.

## Hallucination control

1. Minimum similarity threshold on retrieval.
2. Dedicated sufficiency node (similarity floor + LLM check) before answering.
3. Prompt restricted to the retrieved context.
4. Explicit refusal: *"No tengo suficiente información en mi base de conocimiento para responder esa pregunta."*
5. Sources (file, page, snippet) shown with every answer.

## Deployment

| Piece | Platform | Notes |
|-------|----------|-------|
| Frontend | Vercel | Root `frontend/`, config in `frontend/vercel.json`. Set `apiUrl` in `src/environments/environment.ts` to the backend URL before building. |
| Backend | Render (Docker) | Root `backend/`, uses `backend/Dockerfile`. Environment variables: see `.env.example`. |
| LLM | Ollama on a machine you control | Expose it with a tunnel (e.g. Cloudflare Tunnel) and set `OLLAMA_HOST` on the backend. The models are local by design: no commercial API is used. |

Production URLs: _fill in after deploying_
- Frontend: https://...
- Backend: https://...

## Repository layout

```
backend/    FastAPI app (app/), tests/, migrations/, scripts/, Dockerfile
frontend/   Angular app (src/app/{core,features,shared,models}), Dockerfile
docs/       architecture, screenshots, technical report
docker-compose.yml   .env.example
```

## Screenshots

_Add screenshots to `docs/screenshots/` and link them here._

## Team

Lucas Henao, Santiago Cardozo, Luciano Jaramillo. Universidad EIA, Semester 7.
