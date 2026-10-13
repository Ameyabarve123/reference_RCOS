import io

from app.core.errors import AppError
from app.services.router import clean_text


def extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise AppError(
            "pypdf is not installed. From backend/, run: pip install -r requirements.txt",
            503,
        ) from exc

    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    text = clean_text("\n\n".join(pages))
    if not text:
        raise AppError(
            "This PDF has no extractable text. Export it as text, or upload a picture of the page so the LaTeX agent can read it.",
            422,
        )
    return text


def decode_text(data: bytes) -> str:
    text = clean_text(data.decode("utf-8", errors="replace"))
    if not text:
        raise AppError("The file is empty.", 422)
    return text
