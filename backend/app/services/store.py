import logging
import re
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.errors import AppError
from app.core.supabase import friendly_db_error, get_db

logger = logging.getLogger(__name__)

MAX_CHUNKS = 60


def _rows(response: Any) -> list[dict]:
    data = getattr(response, "data", None)
    if isinstance(data, list):
        return data
    return []


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in values) + "]"


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")[:120]
    return cleaned or "upload"


class Store:
    def __init__(self) -> None:
        self.client = get_db()

    def _run(self, operation):
        try:
            return operation()
        except AppError:
            raise
        except Exception as exc:
            raise friendly_db_error(exc) from exc

    def upsert_person(self, user, profile: dict | None = None) -> dict:
        meta = dict(getattr(user, "user_metadata", None) or {})
        for key, value in (profile or {}).items():
            if value:
                meta[key] = value
        phone = str(meta.get("phone_number") or "").strip() or None
        uid = str(user.id)
        payload = {
            "uid": uid,
            "email": user.email,
            "first_name": str(meta.get("first_name") or "").strip(),
            "last_name": str(meta.get("last_name") or "").strip(),
            "phone_number": phone,
        }

        def write():
            existing = (
                self.client.table("person")
                .select("uid, is_admin")
                .eq("uid", uid)
                .limit(1)
                .execute()
            )
            if _rows(existing):
                updated = (
                    self.client.table("person")
                    .update(
                        {
                            "email": payload["email"],
                            "first_name": payload["first_name"],
                            "last_name": payload["last_name"],
                            "phone_number": payload["phone_number"],
                        }
                    )
                    .eq("uid", uid)
                    .execute()
                )
                return _rows(updated)[0]
            created = self.client.table("person").insert(payload).execute()
            return _rows(created)[0]

        person = self._run(write)
        self.ensure_library_folder(uid)
        return person

    def get_person(self, uid: str) -> dict | None:
        def read():
            response = (
                self.client.table("person")
                .select("uid, first_name, last_name, email, phone_number, timestamp, is_admin")
                .eq("uid", uid)
                .limit(1)
                .execute()
            )
            rows = _rows(response)
            return rows[0] if rows else None

        return self._run(read)

    def ensure_library_folder(self, person_uid: str) -> dict:
        def read():
            response = (
                self.client.table("folder")
                .select("id, name, timestamp")
                .eq("person_uid", person_uid)
                .eq("name", "Library")
                .limit(1)
                .execute()
            )
            rows = _rows(response)
            if rows:
                return rows[0]
            created = (
                self.client.table("folder")
                .insert({"name": "Library", "person_uid": person_uid})
                .execute()
            )
            return _rows(created)[0]

        return self._run(read)

    def list_folders(self, person_uid: str) -> list[dict]:
        def read():
            response = (
                self.client.table("folder")
                .select("id, name, timestamp")
                .eq("person_uid", person_uid)
                .order("timestamp")
                .execute()
            )
            return _rows(response)

        return self._run(read)

    def create_folder(self, person_uid: str, name: str) -> dict:
        def write():
            response = (
                self.client.table("folder")
                .insert({"name": name.strip(), "person_uid": person_uid})
                .execute()
            )
            return _rows(response)[0]

        return self._run(write)

    def owned_folder(self, person_uid: str, folder_id: str) -> dict | None:
        def read():
            response = (
                self.client.table("folder")
                .select("id, name, timestamp")
                .eq("id", folder_id)
                .eq("person_uid", person_uid)
                .limit(1)
                .execute()
            )
            rows = _rows(response)
            return rows[0] if rows else None

        return self._run(read)

    def provider_id(self) -> str:
        def read():
            response = (
                self.client.table("ai_provider")
                .select("id")
                .eq("name", "gemini")
                .limit(1)
                .execute()
            )
            rows = _rows(response)
            if rows:
                return rows[0]["id"]
            created = self.client.table("ai_provider").insert({"name": "gemini"}).execute()
            return _rows(created)[0]["id"]

        return self._run(read)

    def insert_file(
        self,
        *,
        file_id: str,
        filename: str,
        content_type: str | None,
        s3_key: str,
        url: str,
    ) -> dict:
        def write():
            response = (
                self.client.table("files")
                .insert(
                    {
                        "id": file_id,
                        "filename": filename,
                        "content_type": content_type,
                        "s3_key": s3_key,
                        "url": url,
                    }
                )
                .execute()
            )
            return _rows(response)[0]

        return self._run(write)

    def upload_object(self, key: str, data: bytes, content_type: str) -> str:
        bucket = settings.storage_bucket

        def write():
            self.client.storage.from_(bucket).upload(
                key,
                data,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            return self.client.storage.from_(bucket).get_public_url(key)

        return self._run(write)

    def remove_object(self, key: str | None) -> None:
        if not key:
            return
        try:
            self.client.storage.from_(settings.storage_bucket).remove([key])
        except Exception:
            logger.info("storage object already gone: %s", key)

    def insert_text(self, data: str) -> dict:
        def write():
            response = self.client.table("texts").insert({"data": data}).execute()
            return _rows(response)[0]

        return self._run(write)

    def link(self, person_uid: str, folder_id: str, *, file_id: str | None = None, text_id: str | None = None) -> None:
        def write():
            self.client.table("folder_containing_files_text").insert(
                {
                    "person_uid": person_uid,
                    "folder_id": folder_id,
                    "file_id": file_id,
                    "text_id": text_id,
                }
            ).execute()

        self._run(write)

    def insert_chunks(
        self,
        chunks: list[str],
        *,
        provider_id: str,
        file_id: str | None = None,
        text_id: str | None = None,
    ) -> list[str]:
        rows = [
            {
                "id": str(uuid.uuid4()),
                "chunk": chunk,
                "file_id": file_id,
                "text_id": text_id,
                "ai_provider_id": provider_id,
            }
            for chunk in chunks
        ]

        def write():
            self.client.table("chunks").insert(rows).execute()
            return [row["id"] for row in rows]

        return self._run(write)

    def insert_embeddings(self, chunk_ids: list[str], vectors: list[list[float]], provider_id: str) -> None:
        embedding_rows = [
            {
                "id": str(uuid.uuid4()),
                "chunk_id": chunk_id,
                "embedding": vector_literal(vector),
            }
            for chunk_id, vector in zip(chunk_ids, vectors)
        ]
        uses = [
            {"ai_provider_id": provider_id, "embedding_id": row["id"]}
            for row in embedding_rows
        ]

        def write():
            self.client.table("embeddings").insert(embedding_rows).execute()
            if uses:
                self.client.table("uses").insert(uses).execute()

        self._run(write)

    def delete_file_row(self, file_id: str) -> None:
        def write():
            self.client.table("files").delete().eq("id", file_id).execute()

        self._run(write)

    def delete_text_row(self, text_id: str) -> None:
        def write():
            self.client.table("texts").delete().eq("id", text_id).execute()

        self._run(write)

    def owned_file(self, person_uid: str, file_id: str) -> dict | None:
        def read():
            link = (
                self.client.table("folder_containing_files_text")
                .select("file_id")
                .eq("person_uid", person_uid)
                .eq("file_id", file_id)
                .limit(1)
                .execute()
            )
            if not _rows(link):
                return None
            response = (
                self.client.table("files")
                .select("id, s3_key, filename")
                .eq("id", file_id)
                .limit(1)
                .execute()
            )
            rows = _rows(response)
            return rows[0] if rows else None

        return self._run(read)

    def owned_text(self, person_uid: str, text_id: str) -> dict | None:
        def read():
            link = (
                self.client.table("folder_containing_files_text")
                .select("text_id")
                .eq("person_uid", person_uid)
                .eq("text_id", text_id)
                .limit(1)
                .execute()
            )
            rows = _rows(link)
            return rows[0] if rows else None

        return self._run(read)

    def library(self, person_uid: str) -> dict:
        folders = self.list_folders(person_uid)

        def read_links():
            response = (
                self.client.table("folder_containing_files_text")
                .select("folder_id, file_id, text_id")
                .eq("person_uid", person_uid)
                .execute()
            )
            return _rows(response)

        links = self._run(read_links)
        file_ids = [row["file_id"] for row in links if row.get("file_id")]
        text_ids = [row["text_id"] for row in links if row.get("text_id")]
        files = self._by_ids(
            "files",
            file_ids,
            "id, filename, content_type, timestamp, url",
        )
        texts = self._by_ids("texts", text_ids, "id, data, timestamp")
        counts = self._chunk_counts(file_ids, text_ids)

        items: list[dict] = []
        for link in links:
            if link.get("file_id") and link["file_id"] in files:
                record = files[link["file_id"]]
                items.append(
                    {
                        "id": record["id"],
                        "kind": "file",
                        "name": record["filename"],
                        "folder_id": link["folder_id"],
                        "timestamp": record["timestamp"],
                        "chunk_count": counts.get(("file", record["id"]), 0),
                    }
                )
            elif link.get("text_id") and link["text_id"] in texts:
                record = texts[link["text_id"]]
                preview = re.sub(r"\s+", " ", record["data"]).strip()
                items.append(
                    {
                        "id": record["id"],
                        "kind": "text",
                        "name": preview[:80] or "Note",
                        "folder_id": link["folder_id"],
                        "timestamp": record["timestamp"],
                        "chunk_count": counts.get(("text", record["id"]), 0),
                    }
                )
        items.sort(key=lambda item: item["timestamp"], reverse=True)
        return {"folders": folders, "items": items}

    def _by_ids(self, table: str, ids: list[str], columns: str) -> dict[str, dict]:
        if not ids:
            return {}

        def read():
            response = self.client.table(table).select(columns).in_("id", ids).execute()
            return {row["id"]: row for row in _rows(response)}

        return self._run(read)

    def _chunk_counts(self, file_ids: list[str], text_ids: list[str]) -> dict[tuple[str, str], int]:
        counts: dict[tuple[str, str], int] = {}

        def tally(column: str, ids: list[str], kind: str):
            if not ids:
                return
            response = (
                self.client.table("chunks").select(column).in_(column, ids).limit(1000).execute()
            )
            for row in _rows(response):
                key = (kind, row[column])
                counts[key] = counts.get(key, 0) + 1

        def read():
            tally("file_id", file_ids, "file")
            tally("text_id", text_ids, "text")
            return counts

        return self._run(read)

    def list_chats(self, person_uid: str) -> list[dict]:
        def read():
            response = (
                self.client.table("chats")
                .select("id, chat_name, timestamp")
                .eq("person_uid", person_uid)
                .order("timestamp", desc=True)
                .execute()
            )
            return _rows(response)

        return self._run(read)

    def create_chat(self, person_uid: str, chat_name: str) -> dict:
        def write():
            response = (
                self.client.table("chats")
                .insert({"person_uid": person_uid, "chat_name": chat_name.strip() or "New chat"})
                .execute()
            )
            return _rows(response)[0]

        return self._run(write)

    def get_chat(self, person_uid: str, chat_id: str) -> dict | None:
        def read():
            response = (
                self.client.table("chats")
                .select("id, chat_name, timestamp, person_uid")
                .eq("id", chat_id)
                .eq("person_uid", person_uid)
                .limit(1)
                .execute()
            )
            rows = _rows(response)
            return rows[0] if rows else None

        return self._run(read)

    def rename_chat(self, chat_id: str, chat_name: str) -> None:
        def write():
            self.client.table("chats").update({"chat_name": chat_name}).eq("id", chat_id).execute()

        self._run(write)

    def delete_chat(self, person_uid: str, chat_id: str) -> bool:
        chat = self.get_chat(person_uid, chat_id)
        if chat is None:
            return False

        def write():
            self.client.table("chats").delete().eq("id", chat_id).execute()

        self._run(write)
        return True

    def messages(self, chat_id: str) -> list[dict]:
        def read():
            response = (
                self.client.table("messages")
                .select("message_id, chat_id, timestamp, message, role, query_mode")
                .eq("chat_id", chat_id)
                .order("timestamp")
                .execute()
            )
            return _rows(response)

        rows = self._run(read)
        citations = self.citations_for_chat(chat_id)
        for row in rows:
            row["citations"] = citations.get(row["message_id"], [])
        return rows

    def citations_for_chat(self, chat_id: str) -> dict[str, list[dict]]:
        def read_refs():
            response = (
                self.client.table("chunk_references")
                .select("message_id, chunk_id, similarity")
                .eq("chat_id", chat_id)
                .execute()
            )
            return _rows(response)

        refs = self._run(read_refs)
        chunk_ids = list({row["chunk_id"] for row in refs})
        chunks = self._by_ids("chunks", chunk_ids, "id, chunk, file_id, text_id")
        file_ids = [row["file_id"] for row in chunks.values() if row.get("file_id")]
        text_ids = [row["text_id"] for row in chunks.values() if row.get("text_id")]
        files = self._by_ids("files", file_ids, "id, filename")
        texts = self._by_ids("texts", text_ids, "id, data")

        grouped: dict[str, list[dict]] = {}
        for row in refs:
            chunk = chunks.get(row["chunk_id"], {})
            source = "document"
            if chunk.get("file_id") and chunk["file_id"] in files:
                source = files[chunk["file_id"]]["filename"]
            elif chunk.get("text_id") and chunk["text_id"] in texts:
                source = " ".join(texts[chunk["text_id"]]["data"].split())[:80] or "Note"
            grouped.setdefault(row["message_id"], []).append(
                {
                    "chunk_id": row["chunk_id"],
                    "excerpt": (chunk.get("chunk") or "")[:500],
                    "source": source,
                    "similarity": row.get("similarity"),
                }
            )
        return grouped

    def insert_message(
        self,
        *,
        chat_id: str,
        message: str,
        role: str,
        query_mode: str | None = None,
    ) -> dict:
        def write():
            response = (
                self.client.table("messages")
                .insert(
                    {
                        "chat_id": chat_id,
                        "message": message,
                        "role": role,
                        "query_mode": query_mode,
                    }
                )
                .execute()
            )
            return _rows(response)[0]

        return self._run(write)

    def insert_references(self, chat_id: str, message_id: str, citations: list[dict]) -> None:
        if not citations:
            return
        rows = [
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "chunk_id": citation["chunk_id"],
                "similarity": citation.get("similarity"),
            }
            for citation in citations
        ]

        def write():
            self.client.table("chunk_references").insert(rows).execute()

        self._run(write)

    def match_chunks(self, person_uid: str, vector: list[float], match_count: int = 20) -> list[dict]:
        def read():
            response = self.client.rpc(
                "match_chunks",
                {
                    "query_embedding": vector_literal(vector),
                    "match_count": match_count,
                    "owner": person_uid,
                },
            ).execute()
            return _rows(response)

        return self._run(read)
