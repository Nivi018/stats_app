from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.api.routes.matchday import router as matchday_router
from app.api.routes.parlay import router as parlay_router
from app.api.routes.evaluation import router as evaluation_router
from app.api.routes.ops import router as ops_router
from app.core.config import settings
from app.core.errors import setup_error_handlers
from app.core.health import router as health_router
from app.core.logging import setup_logging
from app.core.observability import request_observability_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(
    title="Stats App API",
    version="0.1.0",
    lifespan=lifespan,
)

setup_error_handlers(app)
app.middleware("http")(request_observability_middleware)

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(health_router, tags=["health"])
v1_router.include_router(matchday_router, tags=["matchday"])
v1_router.include_router(parlay_router, tags=["parlay"])
v1_router.include_router(evaluation_router, tags=["evaluation"])
v1_router.include_router(ops_router, tags=["ops"])
app.include_router(v1_router)


@app.get("/")
async def root():
    return {"service": "stats-api", "version": settings.VERSION, "env": settings.ENV}
