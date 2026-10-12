"""The groups: list them, and make one of two to six active bots."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from harness.bots import BotNotFound, BotService, Group, GroupDraft

logger = logging.getLogger(__name__)


def build_router(bots: BotService) -> APIRouter:
    """Every group, and making one; a member that is no active bot is a 422."""
    router = APIRouter(prefix="/api/groups", tags=["groups"])

    @router.get("", response_model=list[Group])
    async def list_groups() -> list[Group]:
        return list(bots.groups())

    @router.post("", status_code=status.HTTP_201_CREATED, response_model=Group)
    async def create_group(body: GroupDraft) -> Group:
        try:
            group = await bots.create_group(body)
        except BotNotFound as err:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)) from err
        logger.info("group %s created with %s", group.id, list(group.member_ids))
        return group

    return router
