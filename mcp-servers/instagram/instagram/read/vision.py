"""Frames to on-screen text and a scene description, in one call.

**One call, not two, and that is a measured decision.** `glm-5.3-flash` read a
reel's text overlay as accurately as the dedicated OCR model *while also*
identifying the location from terrain and architecture — on a live reel it
returned "Rajgad Fort … Pune district, Maharashtra" from frames alone, and named
the ridge spur. So asking separately for text and for scene would double the
cost of the common case where both are wanted.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from instagram.read.http import ProviderHttp, message_text, strip_sentinels

# The two labels the prompt asks for. Markers rather than JSON because a vision
# model asked for JSON returns it inside a code fence often enough that a parse
# failure would cost the whole read.
_TEXT_MARKER = "ON-SCREEN TEXT:"
_SCENE_MARKER = "SCENE:"

VISION_PROMPT = (
    "These are frames sampled in order from one Instagram reel. Reply in exactly two labelled "
    f"sections and nothing else.\n\n{_TEXT_MARKER}\nEvery piece of text visible in the frames, "
    "transcribed verbatim, one item per line. Write NONE if there is no legible text.\n\n"
    f"{_SCENE_MARKER}\nWhat the frames show: the kind of place, the terrain or interior, the "
    "architecture, any food or products, signage, and what a visitor would do there. If the "
    "frames strongly indicate a specific named place, say which and what visual evidence "
    "supports it."
)


@dataclass(frozen=True)
class Description:
    overlay_text: tuple[str, ...]
    scene: str


async def describe(http: ProviderHttp, frames: Sequence[Path], *, model: str) -> Description:
    """One call over every frame. Returns text and scene, separated."""
    if not frames:
        return Description(overlay_text=(), scene="")

    content: list[dict[str, object]] = [{"type": "text", "text": VISION_PROMPT}]
    for frame in frames:
        encoded = base64.b64encode(frame.read_bytes()).decode("ascii")
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}
        )

    body = await http.post_json(
        "/chat/completions",
        {"model": model, "max_tokens": 900, "messages": [{"role": "user", "content": content}]},
    )
    return parse_description(message_text(body))


def parse_description(raw: str) -> Description:
    """Split the two labelled sections, tolerating a model that ignores them.

    Total by construction: an unlabelled answer becomes the scene rather than an
    error, because a usable description in the wrong shape is still evidence and
    failing the read would throw away a correct place identification over a
    formatting slip.
    """
    text = strip_sentinels(raw)
    upper = text.upper()
    text_at = upper.find(_TEXT_MARKER)
    scene_at = upper.find(_SCENE_MARKER)

    if text_at == -1 and scene_at == -1:
        return Description(overlay_text=(), scene=text)
    if scene_at == -1:
        return Description(overlay_text=_lines(text[text_at + len(_TEXT_MARKER) :]), scene="")
    if text_at == -1:
        return Description(overlay_text=(), scene=text[scene_at + len(_SCENE_MARKER) :].strip())

    return Description(
        overlay_text=_lines(text[text_at + len(_TEXT_MARKER) : scene_at]),
        scene=text[scene_at + len(_SCENE_MARKER) :].strip(),
    )


def _lines(block: str) -> tuple[str, ...]:
    """Non-empty lines, deduplicated, order preserved.

    Deduplicated because the same overlay persists across sampled frames, so a
    twelve-frame read of one caption returns it twelve times otherwise. Bullet
    and quote punctuation is stripped: the model adds it unbidden and it would
    make an otherwise-identical line look distinct.
    """
    seen: list[str] = []
    for line in block.splitlines():
        cleaned = line.strip().lstrip("-*•").strip().strip('"').strip()
        if not cleaned or cleaned.upper() == "NONE":
            continue
        if cleaned not in seen:
            seen.append(cleaned)
    return tuple(seen)
