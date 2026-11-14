"""`GET /api/app-events` — what happened in the app, for every open window."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from harness.app_events import AppEventService
from harness.channels.web.sse import SSE_MEDIA_TYPE, frame, kept_alive


class AppEventRouter:
    """The app events stream over one `AppEventService`."""

    def __init__(self, app_events: AppEventService) -> None:
        self._app_events = app_events
        self.router: APIRouter = APIRouter(prefix="/api/app-events", tags=["app-events"])
        self.router.add_api_route("", self.stream_app_events, methods=["GET"])

    async def stream_app_events(self) -> StreamingResponse:
        return StreamingResponse(
            kept_alive(self._event_stream()),
            media_type=SSE_MEDIA_TYPE,
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def _event_stream(self) -> AsyncGenerator[str]:
        """`app/connected`, then a frame for every event published from now on."""
        yield frame("app/connected", '{"type":"app/connected"}')
        async for event in self._app_events.subscribe():
            yield frame(event.type, event.model_dump_json())
