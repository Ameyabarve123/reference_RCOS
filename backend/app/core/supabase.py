import logging

from supabase import Client, create_client

from app.core.config import settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

_db: Client | None = None


def get_db() -> Client:
    global _db
    if _db is None:
        if not settings.supabase_url or not settings.supabase_key:
            raise AppError("Set SUPABASE_URL and SUPABASE_KEY in backend/.env.", 503)
        _db = create_client(settings.supabase_url, settings.supabase_key)
    return _db


def auth_client() -> Client:
    """Fresh client so a login does not replace the service-role session."""
    if not settings.supabase_url or not settings.supabase_key:
        raise AppError("Set SUPABASE_URL and SUPABASE_KEY in backend/.env.", 503)
    return create_client(settings.supabase_url, settings.supabase_key)


def friendly_db_error(exc: Exception) -> AppError:
    text = str(exc)
    logger.warning("database error: %s", text)
    lowered = text.lower()
    if "match_chunks" in lowered or "does not exist" in lowered or "relation" in lowered:
        return AppError(
            "Database schema is missing. Run supabase/schema.sql in the Supabase SQL editor.",
            503,
        )
    if "bucket" in lowered:
        return AppError(
            "Storage bucket 'documents' is missing. Re-run supabase/schema.sql.",
            503,
        )
    if "duplicate" in lowered or "unique" in lowered:
        return AppError("That email or phone number is already in use.", 409)
    if "row-level security" in lowered or "permission denied" in lowered:
        return AppError(
            "Supabase rejected the write. SUPABASE_KEY must be the secret key, not the anon key.",
            503,
        )
    return AppError("The database request failed. Check the backend logs.", 502)
