"""The Approvals page: which tools run unasked, and taking one back."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from harness.tools import ApprovalService
from harness.tools.router.approval_schemas import ApprovedTools

logger = logging.getLogger(__name__)


class ApprovalRouter:
    """List the standing grants, and revoke one."""

    def __init__(self, approvals: ApprovalService) -> None:
        self._approvals = approvals
        self.router: APIRouter = APIRouter(prefix="/api/approvals", tags=["approvals"])
        self.router.add_api_route(
            "", self.list_approvals, methods=["GET"], response_model=ApprovedTools
        )
        self.router.add_api_route(
            "/{tool}", self.revoke, methods=["DELETE"], status_code=status.HTTP_204_NO_CONTENT
        )

    async def list_approvals(self) -> ApprovedTools:
        return ApprovedTools(tools=sorted(self._approvals.approved_tools()))

    async def revoke(self, tool: str) -> Response:
        self._approvals.revoke(tool)
        logger.info("approval for %s revoked", tool)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
