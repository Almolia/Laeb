from fastapi import APIRouter

from shared_kernel.app import create_app

app = create_app("forum")
router = APIRouter(prefix="/api/v1/forum")


@router.get("/health")
def api_health():
    return {"status": "ok"}


@router.get("/ping")
def ping():
    return {"pong": True}


app.include_router(router)
