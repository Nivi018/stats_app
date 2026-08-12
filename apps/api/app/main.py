from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.core.config import settings
from app.core.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Stats App API",
    version="0.1.0",
    lifespan=lifespan,
)

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(health_router, tags=["health"])
app.include_router(v1_router)


@app.get("/")
async def root():
    return {"service": "stats-api", "version": settings.VERSION, "env": settings.ENV}
