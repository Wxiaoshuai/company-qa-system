from fastapi import FastAPI

from app.api.routes import router as qa_router
from app.core.config import settings

app = FastAPI(title=settings.app_name)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


app.include_router(qa_router)
