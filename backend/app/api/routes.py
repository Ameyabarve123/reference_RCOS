from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.chats import router as chat_router
from app.api.library import router as library_router

router = APIRouter(prefix="/api")
router.include_router(auth_router)
router.include_router(library_router)
router.include_router(chat_router)


@router.get("/")
def api_root() -> dict[str, str]:
    return {"message": "RCOS RAG API"}
