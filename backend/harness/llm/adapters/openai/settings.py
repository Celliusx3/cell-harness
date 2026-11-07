"""Where one model is reached, with what key, and how it is asked."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class OpenAISettings(BaseModel):
    """One OpenAI-compatible endpoint, the model asked there, and its key."""

    model_config = ConfigDict(frozen=True)

    base_url: str
    model: str
    api_key: str
    temperature: float
    timeout_seconds: float
