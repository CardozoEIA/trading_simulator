import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.users.routes import router as users_router
from app.modules.auth.routes import router as auth_router
from app.modules.backtest.routes import router as backtest_router
from app.modules.risk.routes import router as risk_router
from app.modules.simulations.routes import router as simulations_router
from app.modules.portfolio.routes import router as portfolio_router
from app.modules.decisions.routes import router as decisions_router
from app.modules.signals.routes import router as signals_router
from app.modules.agent.routes import router as agent_router
from app.modules.results.routes import router as results_router
from app.modules.insights.routes import router as insights_router
from app.modules.chat.routes import router as chat_router
from app.modules.documents.routes import router as documents_router
from app.modules.knowledge.routes import router as knowledge_router
from app.modules.report.routes import router as report_router
from app.modules.compare.routes import router as compare_router
from app.modules.whatif.routes import router as whatif_router

app = FastAPI(title="Market Navigator AI API")

# Comma-separated list of frontend URLs allowed to call the API (set CORS_ORIGINS in production).
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:4200").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Market Navigator AI API funcionando"}


app.include_router(users_router)
app.include_router(auth_router)
app.include_router(backtest_router)
app.include_router(risk_router)
app.include_router(simulations_router)
app.include_router(portfolio_router)
app.include_router(decisions_router)
app.include_router(signals_router)
app.include_router(agent_router)
app.include_router(results_router)
app.include_router(insights_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(knowledge_router)
app.include_router(report_router)
app.include_router(compare_router)
app.include_router(whatif_router)
