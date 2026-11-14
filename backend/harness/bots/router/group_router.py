"""The groups: list them, and make one of two to six active bots."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from harness.bots import BotNotFound, BotService, Group, GroupDraft, GroupService

logger = logging.getLogger(__name__)


class GroupRouter:
    """Every group, and making one; a member that is no active bot is a 422."""

    def __init__(self, bots: BotService, groups: GroupService) -> None:
        self._bots = bots
        self._groups = groups
        self.router: APIRouter = APIRouter(prefix="/api/groups", tags=["groups"])
        self.router.add_api_route("", self.list_groups, methods=["GET"], response_model=list[Group])
        self.router.add_api_route(
            "",
            self.create_group,
            methods=["POST"],
            status_code=status.HTTP_201_CREATED,
            response_model=Group,
        )

    async def list_groups(self) -> list[Group]:
        return list(self._bots.groups())

    async def create_group(self, body: GroupDraft) -> Group:
        try:
            group = await self._groups.create(body)
        except BotNotFound as err:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)) from err
        logger.info("group %s created with %s", group.id, list(group.member_ids))
        return group
