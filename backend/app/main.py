from fastapi import FastAPI

from app.modules.users.routes import router as users_router
from app.modules.auth.routes import router as auth_router


app = FastAPI(
    title="Market Navigator AI API"
)


@app.get("/")
def root():
    return {
        "message": "Market Navigator AI API funcionando"
    }


app.include_router(users_router)
app.include_router(auth_router)