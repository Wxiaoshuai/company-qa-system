from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth_routes import router as auth_router
from app.api.routes import router as qa_router
from app.core.auth_store import auth_store
from app.core.config import settings

app = FastAPI(title=settings.app_name)
static_dir = Path(__file__).resolve().parent / "static"

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
def on_startup() -> None:
    auth_store.init_db()
    auth_store.ensure_admin_user()


@app.get("/", include_in_schema=False)
def home(request: Request):
    user = auth_store.get_user_by_session_token(request.cookies.get(settings.auth_session_cookie_name))
    if user is None:
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse(static_dir / "index.html")


@app.get("/login", include_in_schema=False)
def login_page(request: Request):
    user = auth_store.get_user_by_session_token(request.cookies.get(settings.auth_session_cookie_name))
    if user is not None:
        return RedirectResponse(url="/", status_code=302)
    return FileResponse(static_dir / "login.html")


@app.get("/admin", include_in_schema=False)
def admin_page(request: Request):
    user = auth_store.get_user_by_session_token(request.cookies.get(settings.auth_session_cookie_name))
    if user is None:
        return RedirectResponse(url="/login", status_code=302)
    if user.role != "admin":
        return HTMLResponse("没有管理员权限。", status_code=403)
    return FileResponse(static_dir / "admin.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


app.include_router(qa_router)
app.include_router(auth_router)
