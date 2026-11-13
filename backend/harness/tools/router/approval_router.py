"""The Approvals page: which tools run unasked, and taking one back."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from harness.tools import ApprovalService
from harness.tools.router.approval_schemas import ApprovedTools

logger = logging.getLogger(__name__)


def build_router(approvals: ApprovalService) -> APIRouter:
    """List the standing grants, and revoke one."""
    router = APIRouter(prefix="/api/approvals", tags=["approvals"])

    @router.get("", response_model=ApprovedTools)
    async def list_approvals() -> ApprovedTools:
        return ApprovedTools(tools=sorted(approvals.approved_tools()))

    @router.delete("/{tool}", status_code=status.HTTP_204_NO_CONTENT)
    async def revoke(tool: str) -> Response:
        approvals.revoke(tool)
        logger.info("approval for %s revoked", tool)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
