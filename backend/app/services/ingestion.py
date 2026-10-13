import uuid

from app.core.errors import AppError
from app.services.chunking import fixed_chunks, semantic_chunks, sentence_chunks
from app.services.extract import decode_text, extract_pdf
from app.services.latex_agent import latex_from_image
from app.services.llm import embed_documents
from app.services.router import choose_strategy, clean_text, route_upload
from app.services.store import MAX_CHUNKS, Store, safe_filename

MAX_FILE_BYTES = 15 * 1024 * 1024


def _split(strategy: str, text: str) -> tuple[list[str], bool]:
    if strategy == "semantic":
        chunks = semantic_chunks(text, embed_documents)
    elif strategy == "sentence":
        chunks = sentence_chunks(text)
    else:
        chunks = fixed_chunks(text)
    cleaned = [chunk for chunk in chunks if chunk.strip()]
    if not cleaned:
        raise AppError("Nothing could be chunked from that document.", 422)
    return cleaned[:MAX_CHUNKS], len(cleaned) > MAX_CHUNKS


def _resolve_folder(store: Store, person_uid: str, folder_id: str | None) -> str:
    if folder_id:
        folder = store.owned_folder(person_uid, folder_id)
        if folder is None:
            raise AppError("Folder not found.", 404)
        return folder["id"]
    return store.ensure_library_folder(person_uid)["id"]


def _store_chunks(
    store: Store,
    *,
    chunks: list[str],
    vectors: list[list[float]],
    provider_id: str,
    file_id: str | None = None,
    text_id: str | None = None,
) -> int:
    if len(vectors) != len(chunks):
        raise AppError("Embedding count did not match the chunks.", 502)
    chunk_ids = store.insert_chunks(
        chunks,
        provider_id=provider_id,
        file_id=file_id,
        text_id=text_id,
    )
    store.insert_embeddings(chunk_ids, vectors, provider_id)
    return len(chunk_ids)


def ingest_file(
    store: Store,
    person_uid: str,
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    folder_id: str | None,
) -> dict:
    if not data:
        raise AppError("The file is empty.", 422)
    if len(data) > MAX_FILE_BYTES:
        raise AppError("Files must be 15 MB or smaller.", 413)

    kind = route_upload(filename, content_type)
    steps = [f"router:{kind}"]
    regions: list[dict] = []

    if kind == "pdf":
        text = extract_pdf(data)
    elif kind == "image":
        mime = (content_type or "image/png").split(";")[0]
        if mime not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
            mime = "image/png"
        extracted = latex_from_image(data, mime)
        text = extracted["text"]
        regions = extracted["regions"]
        steps.append("latex-agent")
        if not text:
            raise AppError("The image did not contain readable text.", 422)
    else:
        text = decode_text(data)

    strategy = choose_strategy(text, kind)
    steps.append(f"chunking:{strategy}")
    chunks, truncated = _split(strategy, text)
    vectors = embed_documents(chunks)
    folder = _resolve_folder(store, person_uid, folder_id)
    provider_id = store.provider_id()
    file_id = str(uuid.uuid4())
    key = f"{person_uid}/{file_id}/{safe_filename(filename)}"
    stored_name = safe_filename(filename)

    store.insert_file(
        file_id=file_id,
        filename=stored_name,
        content_type=content_type,
        s3_key=key,
        url="",
    )
    try:
        url = store.upload_object(key, data, content_type or "application/octet-stream")
        store.client.table("files").update({"url": url, "s3_key": key}).eq("id", file_id).execute()
        store.link(person_uid, folder, file_id=file_id)
        count = _store_chunks(
            store,
            chunks=chunks,
            vectors=vectors,
            provider_id=provider_id,
            file_id=file_id,
        )
    except Exception:
        store.delete_file_row(file_id)
        store.remove_object(key)
        raise

    steps.extend(["embed:text-embedding-004", "store:pgvector"])
    return {
        "id": file_id,
        "kind": "file",
        "document_kind": kind,
        "name": stored_name,
        "folder_id": folder,
        "strategy": strategy,
        "chunk_count": count,
        "truncated": truncated,
        "latex_regions": regions,
        "steps": steps,
    }


def ingest_text(
    store: Store,
    person_uid: str,
    *,
    data: str,
    folder_id: str | None,
) -> dict:
    text = clean_text(data)
    if not text:
        raise AppError("The note is empty.", 422)
    if len(text) > 100_000:
        raise AppError("Notes must be 100,000 characters or fewer.", 413)

    strategy = choose_strategy(text, "text")
    chunks, truncated = _split(strategy, text)
    vectors = embed_documents(chunks)
    folder = _resolve_folder(store, person_uid, folder_id)
    provider_id = store.provider_id()
    record = store.insert_text(text)
    try:
        store.link(person_uid, folder, text_id=record["id"])
        count = _store_chunks(
            store,
            chunks=chunks,
            vectors=vectors,
            provider_id=provider_id,
            text_id=record["id"],
        )
    except Exception:
        store.delete_text_row(record["id"])
        raise

    preview = " ".join(text.split())
    return {
        "id": record["id"],
        "kind": "text",
        "document_kind": "text",
        "name": preview[:80] or "Note",
        "folder_id": folder,
        "strategy": strategy,
        "chunk_count": count,
        "truncated": truncated,
        "latex_regions": [],
        "steps": [f"router:text", f"chunking:{strategy}", "embed:text-embedding-004", "store:pgvector"],
    }
