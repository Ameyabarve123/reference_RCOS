from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_person, get_store
from app.core.errors import AppError
from app.services.query import answer_question
from app.services.store import Store

router = APIRouter(prefix="/chats", tags=["chats"])


class ChatBody(BaseModel):
    chat_name: str = Field(default="New chat", max_length=120)


class MessageBody(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


def _guard(operation):
    try:
        return operation()
    except AppError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc


@router.get("")
def list_chats(
    person: dict = Depends(get_current_person),
    store: Store = Depends(get_store),
) -> dict:
    return _guard(lambda: {"chats": store.list_chats(person["uid"])})


@router.post("")
def create_chat(
    body: ChatBody,
    person: dict = Depends(get_current_person),
    store: Store = Depends(get_store),
) -> dict:
    return _guard(lambda: store.create_chat(person["uid"], body.chat_name))


@router.get("/{chat_id}")
def get_chat(
    chat_id: str,
    person: dict = Depends(get_current_person),
    store: Store = Depends(get_store),
) -> dict:
    def read():
        chat = store.get_chat(person["uid"], chat_id)
        if chat is None:
            raise AppError("Chat not found.", 404)
        chat["messages"] = store.messages(chat_id)
        return chat

    return _guard(read)


@router.delete("/{chat_id}")
def delete_chat(
    chat_id: str,
    person: dict = Depends(get_current_person),
    store: Store = Depends(get_store),
) -> dict:
    def remove():
        if not store.delete_chat(person["uid"], chat_id):
            raise AppError("Chat not found.", 404)
        return {"deleted": chat_id}

    return _guard(remove)


@router.post("/{chat_id}/messages")
def send_message(
    chat_id: str,
    body: MessageBody,
    person: dict = Depends(get_current_person),
    store: Store = Depends(get_store),
) -> dict:
    def ask():
        chat = store.get_chat(person["uid"], chat_id)
        if chat is None:
            raise AppError("Chat not found.", 404)
        return answer_question(store, person["uid"], chat, body.message)

    return _guard(ask)
