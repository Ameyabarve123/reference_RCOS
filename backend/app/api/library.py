from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import get_current_person, get_store
from app.core.errors import AppError
from app.services.ingestion import ingest_file, ingest_text
from app.services.store import Store

router = APIRouter(prefix="/library", tags=["library"])


class FolderBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class NoteBody(BaseModel):
    data: str = Field(min_length=1, max_length=100_000)
    folder_id: str | None = None


def _guard(operation):
    try:
        return operation()
    except AppError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc


@router.get("")
def get_library(
    person: dict = Depends(get_current_person),
    store: Store = Depends(get_store),
) -> dict:
    return _guard(lambda: store.library(person["uid"]))


@router.post("/folders")
def create_folder(
    body: FolderBody,
    person: dict = Depends(get_current_person),
    store: Store = Depends(get_store),
) -> dict:
    return _guard(lambda: store.create_folder(person["uid"], body.name))


@router.post("/notes")
def create_note(
    body: NoteBody,
    person: dict = Depends(get_current_person),
    store: Store = Depends(get_store),
) -> dict:
    return _guard(
        lambda: ingest_text(
            store,
            person["uid"],
            data=body.data,
            folder_id=body.folder_id,
        )
    )


@router.post("/files")
def upload_file(
    file: UploadFile = File(...),
    folder_id: str | None = Form(default=None),
    person: dict = Depends(get_current_person),
    store: Store = Depends(get_store),
) -> dict:
    data = file.file.read()
    return _guard(
        lambda: ingest_file(
            store,
            person["uid"],
            filename=file.filename or "upload",
            content_type=file.content_type,
            data=data,
            folder_id=folder_id,
        )
    )


@router.delete("/files/{file_id}")
def delete_file(
    file_id: str,
    person: dict = Depends(get_current_person),
    store: Store = Depends(get_store),
) -> dict:
    def remove():
        record = store.owned_file(person["uid"], file_id)
        if record is None:
            raise AppError("File not found.", 404)
        store.delete_file_row(file_id)
        store.remove_object(record.get("s3_key"))
        return {"deleted": file_id}

    return _guard(remove)


@router.delete("/notes/{text_id}")
def delete_note(
    text_id: str,
    person: dict = Depends(get_current_person),
    store: Store = Depends(get_store),
) -> dict:
    def remove():
        record = store.owned_text(person["uid"], text_id)
        if record is None:
            raise AppError("Note not found.", 404)
        store.delete_text_row(text_id)
        return {"deleted": text_id}

    return _guard(remove)
