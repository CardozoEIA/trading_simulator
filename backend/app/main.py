from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine
from app.modules.users.routes import router as users_router
from app.modules.auth.routes import router as auth_router


app = FastAPI(
    title="Market Navigator AI",
    description="Plataforma académica de simulación de trading",
    version="1.0.0"
)


app.include_router(users_router)
app.include_router(auth_router)


@app.get("/")
def root():
    return {
        "message": "Market Navigator AI API funcionando"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/database")
def database_test():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "database": "connected"
        }

    except Exception as e:
        return {
            "database": "error",
            "message": str(e)
        }