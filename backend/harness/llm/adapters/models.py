"""The model's context window, as the endpoint reports it.

Claude Code carries a per-model table; an OpenAI-compatible endpoint can carry
it for us. `GET /v1/models` lists every model, and ilmu (like OpenRouter and
vLLM) puts `context_length` on each entry. The per-model `GET /v1/models/{id}`
is not used: ilmu answers it 404, and the list has the field anyway.

`None` means "not said" — LM Studio's listing has only the standard fields —
and the composition root decides what that means for compaction. Nothing here
guesses a number: a wrong window fires compaction on the wrong conversation,
or never.

The listing is parsed into a model rather than walked as raw JSON, so the one
shape we depend on is declared once and a malformed body is a validation error
we catch, not an `AttributeError` three `.get()`s deep.
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from harness.config.sections import LLMSettings

logger = logging.getLogger("harness.llm")


class _Model(BaseModel):
    """One entry of the listing, narrowed to what we read. Extra keys are the
    norm — every provider adds its own — so they are ignored, not rejected."""

    model_config = ConfigDict(extra="ignore")

    id: str
    # Positive when reported, `None` when the field is absent or null. `gt=0`
    # turns a nonsense zero into "not said" rather than a window of nothing.
    context_length: int | None = Field(default=None, gt=0)


class _Listing(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: list[_Model] = []


async def context_length(settings: LLMSettings) -> int | None:
    """`context_length` of `settings.model` from the endpoint's listing, or `None`."""
    url = f"{settings.base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=settings.timeout_seconds) as http:
            response = await http.get(url, headers={"Authorization": f"Bearer {settings.api_key}"})
            response.raise_for_status()
            listing = _Listing.model_validate_json(response.content)
    except (httpx.HTTPError, ValidationError) as err:
        logger.warning("could not read %s: %s", url, err)
        return None
    for entry in listing.data:
        if entry.id == settings.model:
            return entry.context_length
    return None
