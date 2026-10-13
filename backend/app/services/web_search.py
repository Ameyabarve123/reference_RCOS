import html
import logging
import re

import httpx

logger = logging.getLogger(__name__)

_TITLE = re.compile(r'class="result__a"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_SNIPPET = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_HREF = re.compile(r'class="result__a"[^>]*href="([^"]+)"', re.IGNORECASE)
_TAGS = re.compile(r"<[^>]+>")


def _plain(value: str) -> str:
    return html.unescape(_TAGS.sub("", value)).strip()


def search_web(query: str, limit: int = 4) -> list[dict[str, str]]:
    """Best-effort public web context for the +web query route."""
    try:
        response = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "RCOS-RAG/0.1 (research project)"},
            timeout=8.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.info("web search unavailable")
        return []

    titles = [_plain(match) for match in _TITLE.findall(response.text)]
    snippets = [_plain(match) for match in _SNIPPET.findall(response.text)]
    hrefs = _HREF.findall(response.text)
    results: list[dict[str, str]] = []
    for index, title in enumerate(titles):
        if not title:
            continue
        results.append(
            {
                "title": title,
                "snippet": snippets[index] if index < len(snippets) else "",
                "url": hrefs[index] if index < len(hrefs) else "",
            }
        )
        if len(results) >= limit:
            break
    return results
