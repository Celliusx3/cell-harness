"""The groups: list them, and make one of two to six active bots."""

from __future__ import annotations

import logging

from fastapi import APIRouter, status

from harness.groups import Group, GroupDraft, GroupService

logger = logging.getLogger(__name__)


class GroupRouter:
    """Every group, and making one; a member that is no active bot is a 422."""

    def __init__(self, groups: GroupService) -> None:
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
        return list(self._groups.all())

    async def create_group(self, body: GroupDraft) -> Group:
        group = await self._groups.create(body)
        logger.info("group %s created with %s", group.id, list(group.member_ids))
        return group
