from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/")
def api_root() -> dict[str, str]:
    return {"message": "RCOS RAG API — scaffold ready"}
