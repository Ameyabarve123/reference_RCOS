from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.core.errors import AppError
from app.core.supabase import get_db
from app.services.store import Store


def get_store() -> Store:
    return Store()


def get_current_person(
    authorization: Annotated[str | None, Header()] = None,
    store: Store = Depends(get_store),
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in required.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required.")
    try:
        response = get_db().auth.get_user(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Sign in required.") from exc
    user = None if response is None else response.user
    if user is None or not user.email:
        raise HTTPException(status_code=401, detail="Sign in required.")
    try:
        person = store.get_person(str(user.id))
        if person is None:
            person = store.upsert_person(user)
    except AppError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return person
