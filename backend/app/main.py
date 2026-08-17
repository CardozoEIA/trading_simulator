from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.users.routes import router as users_router
from app.modules.auth.routes import router as auth_router
from app.modules.backtest.routes import router as backtest_router

app = FastAPI(
    title="Market Navigator AI API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
def root():
    return {
        "message": "Market Navigator AI API funcionando"
    }


app.include_router(users_router)
app.include_router(auth_router)
app.include_router(backtest_router)