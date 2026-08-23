"""LLM connection settings.

`api_key` and `model` are required with no default. A default API key cannot
exist, and a default model is a *behavioral* choice — it decides what answers
cost and how good they are, and inheriting one silently is exactly the "where did
this come from?" bug the house rules forbid. Starting with neither configured is
an error at startup, not a surprise at the first request.

`temperature` is pinned rather than omitted for the same reason in the other
direction: leaving it out means inheriting whatever the provider currently
defaults to, which can change under us without a single line of our code moving.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HARNESS_LLM_",
        env_file=".env",
        extra="ignore",
    )

    api_key: str = Field(min_length=1)
    model: str = Field(min_length=1)
    # An OpenAI-compatible `/chat/completions` endpoint. Defaulted because the
    # overwhelmingly common case is OpenAI itself, and pointing elsewhere is a
    # deployment fact rather than a behavioral choice.
    base_url: str = "https://api.openai.com/v1"
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    # Whole-request budget. Generous: it bounds a streaming call that may
    # legitimately think for a while, and exists so a hung connection surfaces as
    # a failed turn instead of a process that never returns.
    timeout_seconds: float = Field(default=600.0, gt=0)
