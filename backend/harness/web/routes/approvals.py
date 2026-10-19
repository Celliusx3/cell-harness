"""The Approvals page: which tools run unasked, and taking one back."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict

from harness.tools import Approvals

logger = logging.getLogger(__name__)


class GrantedTools(BaseModel):
    """Every tool the person has allowed always."""

    model_config = ConfigDict(frozen=True)

    tools: list[str]


def build_router(approvals: Approvals) -> APIRouter:
    """List the standing grants, and revoke one."""
    router = APIRouter(prefix="/api/approvals", tags=["approvals"])

    @router.get("", response_model=GrantedTools)
    async def list_approvals() -> GrantedTools:
        return GrantedTools(tools=sorted(approvals.always_allowed_tools()))

    @router.delete("/{tool}", status_code=status.HTTP_204_NO_CONTENT)
    async def revoke(tool: str) -> Response:
        approvals.revoke(tool)
        logger.info("approval for %s revoked", tool)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
