from app.services.jsonutil import parse_json
from app.services.llm import complete, embed_query
from app.services.router import route_query
from app.services.store import Store
from app.services.web_search import search_web


def _rerank(question: str, hits: list[dict], top_k: int = 5) -> list[dict]:
    if len(hits) <= top_k:
        return hits
    preview = "\n".join(
        f"[{index}] {hit.get('chunk', '')[:360]}" for index, hit in enumerate(hits)
    )
    raw = complete(
        "Rerank these passages for the question. Prefer passages that answer it directly.\n"
        f"Question: {question}\n"
        f"{preview}\n"
        f'Return JSON {{"order": [up to {top_k} passage indexes, best first]}}.',
        temperature=0,
    )
    try:
        order = parse_json(raw).get("order")
    except (ValueError, TypeError):
        order = None
    if not isinstance(order, list):
        return hits[:top_k]
    picked: list[dict] = []
    seen: set[int] = set()
    for index in order:
        if isinstance(index, int) and 0 <= index < len(hits) and index not in seen:
            picked.append(hits[index])
            seen.add(index)
        if len(picked) >= top_k:
            break
    return picked or hits[:top_k]


def _generate(question: str, mode: str, passages: list[dict], web: list[dict]) -> tuple[str, list[int]]:
    context_lines = []
    for index, hit in enumerate(passages, start=1):
        source = hit.get("source_name") or "document"
        context_lines.append(f"[{index}] ({source}) {hit.get('chunk', '')[:1200]}")
    web_lines = []
    for index, item in enumerate(web, start=1):
        web_lines.append(f"[W{index}] {item.get('title', '')}: {item.get('snippet', '')}")

    mode_rule = {
        "rag_only": "Use only the numbered passages. If they do not contain the answer, say you cannot find it in the library.",
        "rag_web": "Use the numbered passages and the web results. Prefer the library when they disagree, and say so.",
        "rag_pretrained": "Use the numbered passages first. You may add pretrained knowledge, and mark those sentences as general knowledge.",
    }[mode]

    raw = complete(
        "Answer the question for a research library.\n"
        f"{mode_rule}\n"
        "Cite library passages inline as [1], [2]. Do not invent passage numbers.\n"
        f"Question: {question}\n\n"
        "Passages:\n"
        f"{chr(10).join(context_lines) or '(none)'}\n\n"
        "Web:\n"
        f"{chr(10).join(web_lines) or '(none)'}\n\n"
        'Return JSON {"answer": "markdown answer", "cited": [1, 2]}.',
        temperature=0.2,
    )
    try:
        parsed = parse_json(raw)
        answer = str(parsed.get("answer") or "").strip()
        cited = parsed.get("cited") if isinstance(parsed.get("cited"), list) else []
    except (ValueError, TypeError):
        answer = raw.strip()
        cited = []
    if not answer:
        answer = "I could not produce an answer from the available context."
    indexes = []
    for value in cited:
        if isinstance(value, int) and 1 <= value <= len(passages):
            indexes.append(value - 1)
    return answer, indexes


def _citation(hit: dict) -> dict:
    return {
        "chunk_id": hit["chunk_id"],
        "excerpt": (hit.get("chunk") or "")[:500],
        "source": hit.get("source_name") or "document",
        "similarity": hit.get("similarity"),
    }


def answer_question(store: Store, person_uid: str, chat: dict, question: str) -> dict:
    mode, reason = route_query(question)
    steps = [f"query-router:{mode}"]
    vector = embed_query(question)
    steps.append("embed:text-embedding-004")
    hits = store.match_chunks(person_uid, vector, match_count=20)
    steps.append(f"vector-search:{len(hits)}")
    ranked = _rerank(question, hits)
    steps.append(f"rerank:{len(ranked)}")

    web: list[dict] = []
    if mode == "rag_web":
        web = search_web(question)
        steps.append(f"web:{len(web)}")

    answer, cited_indexes = _generate(question, mode, ranked, web)
    steps.append("generate:gemini")
    chosen = [ranked[index] for index in cited_indexes]
    if not chosen and ranked and mode == "rag_only":
        top = ranked[0]
        if (top.get("similarity") or 0) >= 0.45:
            chosen = [top]
    citations = [_citation(hit) for hit in chosen]

    if (chat.get("chat_name") or "New chat") == "New chat":
        store.rename_chat(chat["id"], question.strip()[:72] or "New chat")

    store.insert_message(chat_id=chat["id"], message=question.strip(), role="user")
    assistant = store.insert_message(
        chat_id=chat["id"],
        message=answer,
        role="assistant",
        query_mode=mode,
    )
    store.insert_references(chat["id"], assistant["message_id"], citations)
    assistant["citations"] = citations
    return {
        "mode": mode,
        "router_reason": reason,
        "steps": steps,
        "assistant_message": assistant,
    }
