import re
from pathlib import Path

from app.services.jsonutil import parse_json
from app.services.llm import complete

PDF_TYPES = {"application/pdf"}
IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
TEXT_TYPES = {"text/plain", "text/markdown", "text/csv", "application/json", "text/x-markdown"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TEXT_EXT = {".txt", ".md", ".csv", ".json", ".markdown"}

DocumentKind = str  # "pdf" | "image" | "text"
ChunkStrategy = str  # "semantic" | "fixed" | "sentence"
QueryMode = str  # "rag_only" | "rag_web" | "rag_pretrained"


def route_upload(filename: str, content_type: str | None) -> DocumentKind:
    """Router agent: PDF, image, or text.

    Unambiguous mime types and extensions are classified directly. Anything
    else is sent to Gemini.
    """
    ext = Path(filename).suffix.lower()
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime in PDF_TYPES or ext == ".pdf":
        return "pdf"
    if mime in IMAGE_TYPES or ext in IMAGE_EXT:
        return "image"
    if mime in TEXT_TYPES or ext in TEXT_EXT:
        return "text"

    raw = complete(
        "Classify this upload for a RAG ingestion router.\n"
        f"Filename: {filename}\n"
        f"Content type: {mime or 'unknown'}\n"
        'Return JSON {"kind": "pdf" | "image" | "text"}.',
        temperature=0,
    )
    try:
        kind = str(parse_json(raw).get("kind", "")).lower()
    except (ValueError, TypeError):
        kind = ""
    if kind in {"pdf", "image", "text"}:
        return kind
    return "text"


def choose_strategy(sample: str, kind: DocumentKind) -> ChunkStrategy:
    """Chunking agent: semantic, fixed, or sentence."""
    excerpt = sample.strip()
    if len(excerpt) < 500:
        return "sentence"
    raw = complete(
        "Choose a chunking strategy for a retrieval corpus.\n"
        "- fixed: forms, code, tables, slides, or very regular text\n"
        "- sentence: short notes, lists, Q&A, dialogue\n"
        "- semantic: essays, papers, and prose that changes topic\n"
        f"Document kind: {kind}\n"
        f"Character length: {len(excerpt)}\n"
        "Excerpt:\n"
        f"{excerpt[:1800]}\n"
        'Return JSON {"strategy": "semantic" | "fixed" | "sentence"}.',
        temperature=0,
    )
    try:
        strategy = str(parse_json(raw).get("strategy", "")).lower()
    except (ValueError, TypeError):
        strategy = ""
    if strategy in {"semantic", "fixed", "sentence"}:
        return strategy
    return "fixed"


def route_query(question: str) -> tuple[QueryMode, str]:
    """Query router: RAG only, RAG + web, or RAG + pretrained knowledge."""
    raw = complete(
        "You route a question in a document RAG app.\n"
        "Modes:\n"
        "- rag_only: answer only from the user's uploaded documents\n"
        "- rag_web: the question needs current public web information as well as documents\n"
        "- rag_pretrained: general knowledge, chit-chat, or a question documents may only partly cover, "
        "so the model may add pretrained knowledge\n"
        f"Question: {question}\n"
        'Return JSON {"mode": "rag_only" | "rag_web" | "rag_pretrained", "reason": "short reason"}.',
        temperature=0,
    )
    try:
        parsed = parse_json(raw)
        mode = str(parsed.get("mode", "")).lower()
        reason = str(parsed.get("reason") or "").strip()
    except (ValueError, TypeError):
        mode = ""
        reason = ""
    if mode not in {"rag_only", "rag_web", "rag_pretrained"}:
        mode = "rag_only"
        reason = reason or "Defaulted to the document corpus."
    return mode, reason or "Routed by the query agent."


def clean_text(value: str) -> str:
    return re.sub(r"\s+\Z", "", value.replace("\x00", "")).strip()
