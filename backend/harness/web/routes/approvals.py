"""The Approvals page: which tools run unasked, and taking one back."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict

from harness.tools.approval import ApprovalGate

logger = logging.getLogger(__name__)


class Approvals(BaseModel):
    """Every tool the person has allowed always."""

    model_config = ConfigDict(frozen=True)

    tools: list[str]


def build_router(gate: ApprovalGate) -> APIRouter:
    """List the standing grants, and revoke one."""
    router = APIRouter(prefix="/api/approvals", tags=["approvals"])

    @router.get("", response_model=Approvals)
    async def list_approvals() -> Approvals:
        return Approvals(tools=sorted(gate.granted()))

    @router.delete("/{tool}", status_code=status.HTTP_204_NO_CONTENT)
    async def revoke(tool: str) -> Response:
        try:
            gate.revoke(tool)
        except KeyError as err:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail=f"{tool!r} is not granted"
            ) from err
        logger.info("approval for %s revoked", tool)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
