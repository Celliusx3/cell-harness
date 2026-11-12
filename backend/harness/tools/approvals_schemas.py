"""The approvals page's request and response bodies."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ApprovedTools(BaseModel):
    """Every tool the person has allowed always."""

    model_config = ConfigDict(frozen=True)

    tools: list[str]
