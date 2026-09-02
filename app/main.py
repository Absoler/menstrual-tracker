"""应用入口：挂载路由与静态前端。"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import db
from .routers import auth, notify, records


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="月经记录助手", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(records.router)
app.include_router(notify.router)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
