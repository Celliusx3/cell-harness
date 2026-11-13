"""`GET /api/app-events` — what happened in the app, for every open window."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from harness.app_events import AppEventService
from harness.channels.web.sse import MEDIA_TYPE, frame, kept_alive


async def _event_stream(app_events: AppEventService) -> AsyncGenerator[str]:
    """`app/connected`, then a frame for every event published from now on."""
    yield frame("app/connected", '{"type":"app/connected"}')
    async for event in app_events.subscribe():
        yield frame(event.type, event.model_dump_json())


def build_router(app_events: AppEventService) -> APIRouter:
    router = APIRouter(prefix="/api/app-events", tags=["app-events"])

    @router.get("")
    async def stream_app_events() -> StreamingResponse:
        return StreamingResponse(
            kept_alive(_event_stream(app_events)),
            media_type=MEDIA_TYPE,
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
