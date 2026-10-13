from app.services.jsonutil import parse_json
from app.services.llm import complete
from app.services.router import clean_text

_PROMPT = """Transcribe this image for a retrieval index.
Find each region of prose, mathematics, or a labeled diagram.
Return JSON only:
{"regions": [{"bbox": [x, y, width, height], "latex": "", "text": ""}]}
bbox values are normalized from 0 to 1, origin at the top-left.
Put mathematics in latex. Put ordinary words in text.
If there is no math, still transcribe the visible words."""


def latex_from_image(data: bytes, mime: str) -> dict:
    """LaTeX agent: bounding boxes to LaTeX, plus a plain transcription."""
    raw = complete(_PROMPT, temperature=0, images=[(mime, data)])
    regions: list[dict] = []
    try:
        parsed = parse_json(raw)
        incoming = parsed.get("regions")
        if isinstance(incoming, list):
            for region in incoming:
                if not isinstance(region, dict):
                    continue
                bbox = region.get("bbox")
                if not (isinstance(bbox, list) and len(bbox) == 4):
                    bbox = [0, 0, 1, 1]
                regions.append(
                    {
                        "bbox": [float(value) for value in bbox],
                        "latex": str(region.get("latex") or "").strip(),
                        "text": str(region.get("text") or "").strip(),
                    }
                )
    except (ValueError, TypeError):
        regions = [{"bbox": [0, 0, 1, 1], "latex": "", "text": raw.strip()}]

    lines: list[str] = []
    for index, region in enumerate(regions, start=1):
        bbox = ", ".join(f"{value:.3f}" for value in region["bbox"])
        lines.append(f"[region {index} bbox={bbox}]")
        if region["latex"]:
            lines.append(region["latex"])
        if region["text"]:
            lines.append(region["text"])
    text = clean_text("\n".join(lines))
    if not text:
        text = clean_text(raw)
    return {"text": text, "regions": regions}
