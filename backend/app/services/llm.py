import base64

from app.core.config import settings
from app.core.errors import AppError
from app.services.jsonutil import message_text


def require_google() -> None:
    if not settings.google_api_key:
        raise AppError("Set GOOGLE_API_KEY in backend/.env.", 503)


def _chat(temperature: float):
    require_google()
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise AppError(
            "langchain-google-genai is not installed. From backend/, run: pip install -r requirements.txt",
            503,
        ) from exc
    return ChatGoogleGenerativeAI(
        model=settings.gemini_chat_model,
        google_api_key=settings.google_api_key,
        temperature=temperature,
    )


def _embedder():
    require_google()
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
    except ImportError as exc:
        raise AppError(
            "langchain-google-genai is not installed. From backend/, run: pip install -r requirements.txt",
            503,
        ) from exc
    return GoogleGenerativeAIEmbeddings(
        model=settings.gemini_embed_model,
        google_api_key=settings.google_api_key,
    )


def complete(
    prompt: str,
    *,
    temperature: float = 0.2,
    images: list[tuple[str, bytes]] | None = None,
) -> str:
    llm = _chat(temperature)
    if images:
        from langchain_core.messages import HumanMessage

        content: list[dict] = [{"type": "text", "text": prompt}]
        for mime, data in images:
            encoded = base64.b64encode(data).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                }
            )
        result = llm.invoke([HumanMessage(content=content)])
    else:
        result = llm.invoke(prompt)
    return message_text(result.content)


def _check_dimensions(vectors: list[list[float]]) -> list[list[float]]:
    expected = settings.embedding_dimensions
    for vector in vectors:
        if len(vector) != expected:
            raise AppError(
                f"Embed model returned {len(vector)} dimensions; schema.sql expects {expected}. "
                "Use models/text-embedding-004 or change both the model and the vector column together.",
                502,
            )
    return vectors


def embed_documents(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = _embedder().embed_documents(texts)
    return _check_dimensions(vectors)


def embed_query(text: str) -> list[float]:
    vector = _embedder().embed_query(text)
    return _check_dimensions([vector])[0]
