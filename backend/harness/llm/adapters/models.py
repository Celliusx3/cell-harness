"""The model's context window, as the endpoint reports it."""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from harness.config.sections import LLMSettings

logger = logging.getLogger("harness.llm")


class _Model(BaseModel):
    """One entry of the listing, narrowed to what we read."""

    model_config = ConfigDict(extra="ignore")

    id: str
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
