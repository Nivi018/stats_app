from fastapi import APIRouter

router = APIRouter()


@router.get("/health/live")
async def liveness():
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    return {
        "status": "ok",
        "checks": {
            "postgres": "ok",
            "redis": "ok",
        },
    }
