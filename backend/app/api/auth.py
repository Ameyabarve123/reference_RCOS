from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_person
from app.core.errors import AppError
from app.core.supabase import auth_client
from app.services.store import Store

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def me(person: dict = Depends(get_current_person)) -> dict:
    return person


class SignupBody(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=6, max_length=200)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone_number: str | None = Field(default=None, max_length=30)


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class RefreshBody(BaseModel):
    refresh_token: str = Field(min_length=10)


def _raise_auth(exc: Exception) -> None:
    message = getattr(exc, "message", None) or "Authentication failed."
    status = getattr(exc, "status", None)
    code = 400 if isinstance(status, int) and 400 <= status < 500 else 400
    raise HTTPException(status_code=code, detail=str(message)) from exc


def _metadata(body: SignupBody) -> dict:
    phone = (body.phone_number or "").strip()
    meta = {
        "first_name": body.first_name.strip(),
        "last_name": body.last_name.strip(),
    }
    if phone:
        meta["phone_number"] = phone
    return meta


def _session(auth_response, person: dict | None) -> dict:
    session = auth_response.session
    payload: dict = {
        "person": person,
        "confirmation_required": session is None,
    }
    if session is not None:
        payload["session"] = {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at": session.expires_at,
        }
    return payload


@router.post("/signup")
def signup(body: SignupBody) -> dict:
    email = body.email.strip().lower()
    try:
        response = auth_client().auth.sign_up(
            {
                "email": email,
                "password": body.password,
                "options": {"data": _metadata(body)},
            }
        )
    except Exception as exc:
        _raise_auth(exc)
    if response.user is None:
        raise HTTPException(status_code=400, detail="Could not create the account.")
    try:
        person = Store().upsert_person(response.user, _metadata(body))
    except AppError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return _session(response, person)


@router.post("/login")
def login(body: LoginBody) -> dict:
    try:
        response = auth_client().auth.sign_in_with_password(
            {"email": body.email.strip().lower(), "password": body.password}
        )
    except Exception as exc:
        _raise_auth(exc)
    if response.session is None or response.user is None:
        raise HTTPException(status_code=400, detail="Confirm your email, then sign in.")
    try:
        person = Store().upsert_person(response.user)
    except AppError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return _session(response, person)


@router.post("/refresh")
def refresh(body: RefreshBody) -> dict:
    try:
        response = auth_client().auth.refresh_session(body.refresh_token)
    except Exception as exc:
        _raise_auth(exc)
    if response.session is None:
        raise HTTPException(status_code=401, detail="Session expired. Sign in again.")
    return _session(response, None)
