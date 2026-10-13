import math
import re

_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for piece in _SENTENCE.split(text.strip()):
        for paragraph in re.split(r"\n{2,}", piece):
            line = paragraph.strip()
            if line:
                sentences.append(line)
    return sentences or ([text.strip()] if text.strip() else [])


def fixed_chunks(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = [part.strip() for part in splitter.split_text(text) if part.strip()]
    return chunks or [text.strip()]


def sentence_chunks(text: str, max_chars: int = 800) -> list[str]:
    sentences = split_sentences(text)
    chunks: list[str] = []
    buffer = ""
    for sentence in sentences:
        if buffer and len(buffer) + len(sentence) + 1 > max_chars:
            chunks.append(buffer)
            buffer = sentence
        elif buffer:
            buffer = f"{buffer} {sentence}"
        else:
            buffer = sentence
    if buffer:
        chunks.append(buffer)
    return chunks or [text.strip()]


def _cosine(left: list[float], right: list[float]) -> float:
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right):
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / math.sqrt(left_norm * right_norm)


def semantic_chunks(
    text: str,
    embed_documents,
    *,
    max_chars: int = 1200,
    similarity_threshold: float = 0.72,
) -> list[str]:
    """Group sentences until adjacent embeddings diverge or the chunk fills up."""
    sentences = split_sentences(text)
    if len(sentences) < 3 or len(sentences) > 80:
        return fixed_chunks(text)

    vectors = embed_documents(sentences)
    if len(vectors) != len(sentences):
        return fixed_chunks(text)

    groups: list[list[str]] = [[sentences[0]]]
    for index in range(1, len(sentences)):
        similarity = _cosine(vectors[index - 1], vectors[index])
        current = sum(len(part) for part in groups[-1])
        if similarity < similarity_threshold or current + len(sentences[index]) > max_chars:
            groups.append([sentences[index]])
        else:
            groups[-1].append(sentences[index])
    return [" ".join(group).strip() for group in groups if group]
