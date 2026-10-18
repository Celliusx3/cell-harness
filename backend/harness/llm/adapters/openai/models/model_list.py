"""OpenAI's list of models, narrowed to what the adapter reads."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelInfo(BaseModel):
    """What the endpoint says about one model: its id, and its context window if reported."""

    model_config = ConfigDict(extra="ignore")

    id: str
    context_length: int | None = Field(default=None, gt=0)


class ModelList(BaseModel):
    """The endpoint's reply to `GET /models`."""

    model_config = ConfigDict(extra="ignore")

    data: list[ModelInfo] = []
