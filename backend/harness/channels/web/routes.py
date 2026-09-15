"""Conversations: list, read, send, stream, stop.

Six endpoints, all under `/api/conversations`. The shape worth stating up front is
the handoff between the two reads:

    GET /{id}                 -> events 0..n, next_cursor = n
    GET /{id}/events?after=n  -> n onward, live, then `end`

**Snapshot first, then subscribe at `next_cursor`.** That order cannot lose an
event; the reverse can deliver one twice. And because the stream serves a stored
tail when no turn is running, the handoff is safe however the timing falls — see
`stream_events`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from harness.channels.commands import unknown_skill
from harness.channels.protocol import InboundMessage
from harness.channels.web.schemas import (
    ConversationDetail,
    ConversationSummary,
    MessageAccepted,
    SendMessage,
)
from harness.channels.web.sse import MEDIA_TYPE, Source, sse_frames
from harness.session.log import Session
from harness.session.repository import (
    SessionCorruptionError,
    SessionFormatUnsupportedError,
    SessionNotFoundError,
)
from harness.session.service import SessionService
from harness.skills import UnknownSkill

if TYPE_CHECKING:
    from harness.channels.web.channel import WebChannel


def _unknown_skill(web: WebChannel, err: UnknownSkill) -> HTTPException:
    """`/word` that is neither a command nor a skill — the same sentence
    Telegram and Discord send, as the `detail` the error bar shows."""
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=unknown_skill(err.name, web.gateway.skills.invocable()),
    )


def _summary(session: Session) -> ConversationSummary:
    header = session.header
    return ConversationSummary(id=header.id, created_at=header.created_at, title=header.title)


async def _load(service: SessionService, conversation_id: str, *, for_writing: bool) -> Session:
    """Fetch a stored conversation, mapping its failures onto status codes.

    `for_writing` picks `resume` (which commits crash repair) over `read` (which
    does not). A page view must not write, and after a crash it should show what
    happened rather than the synthetic results that exist to make a *provider*
    accept the history.
    """
    try:
        if for_writing:
            return await service.resume(conversation_id)
        return await service.read(conversation_id)
    except SessionNotFoundError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except (SessionCorruptionError, SessionFormatUnsupportedError) as err:
        # Not the client's fault, and the message names the file and line an
        # operator needs — so it is passed through whole rather than swallowed
        # into a bare 500.
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err)) from err


def build_router(web: WebChannel) -> APIRouter:
    """The browser's endpoints, bound to one channel.

    A factory rather than a module-level router so the handlers close over the
    channel that owns them. They used to read `request.app.state`, which made
    every route depend on how the app happened to be assembled; now what a route
    needs is passed to it.
    """
    router = APIRouter(prefix="/api/conversations", tags=["conversations"])

    @router.get("", response_model=list[ConversationSummary])
    async def list_conversations() -> list[ConversationSummary]:
        """Every stored conversation, newest first."""
        return [
            ConversationSummary(id=h.id, created_at=h.created_at, title=h.title)
            for h in await web.sessions.list()
        ]

    @router.post("", status_code=status.HTTP_201_CREATED, response_model=ConversationSummary)
    async def create_conversation(body: SendMessage) -> ConversationSummary:
        """Start a new conversation with its first message.

        Creating and sending are one call because phase 3's `create()` is lazily
        materialized: it writes nothing, so a bodyless create would hand back an id
        that is absent from the list and gone on refresh. The first message is what
        makes a conversation exist.

        `title` is empty in this response. It is stamped from the first user message
        at the first flush, which happens inside the turn that has only just started —
        so a client shows the text it just sent and lets the next list correct it.
        """
        session = await web.sessions.create()
        # Through the gateway, so a browser conversation gets the same `ChatState`
        # a Telegram one has and can therefore queue. Not `receive()`, though:
        # `create()` has written nothing yet, so this conversation is absent from
        # disk and `on_missing="raise"` would 404 the id we just made.
        try:
            await web.gateway.start_turn(session, body.prompt, channel=web.channel)
        except UnknownSkill as err:
            # Nothing was written: `create()` is lazy, so the refused id never
            # appears in the list.
            raise _unknown_skill(web, err) from err
        return _summary(session)

    @router.get("/{conversation_id}", response_model=ConversationDetail)
    async def get_conversation(conversation_id: str) -> ConversationDetail:
        """The whole log, and the cursor to start streaming from.

        Reads the **live** session when a turn is running. Going to disk instead would
        return fewer events than the log holds — flushes happen at checkpoints, not
        per event — which is harmless for the cursor but shows a client a conversation
        that is mysteriously behind.
        """
        run = web.runs.active(conversation_id)
        session = (
            run.session
            if run is not None
            else await _load(web.sessions, conversation_id, for_writing=False)
        )
        events = list(session.events())
        header = session.header
        return ConversationDetail(
            id=header.id,
            created_at=header.created_at,
            title=header.title,
            events=events,
            next_cursor=len(events),
            running=run is not None,
        )

    @router.post(
        "/{conversation_id}/messages",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=MessageAccepted,
    )
    async def send_message(conversation_id: str, body: SendMessage) -> MessageAccepted:
        """Continue a conversation. Queued if it is already working.

        **This used to be a `409`.** Refusing is the one thing a chat product can
        afford least: it makes someone retype what they already wrote. Telegram
        could never refuse — a phone cannot grey out its composer — so the two
        channels answered the same question differently until this phase, and the
        queue is the answer that was already proven.

        The busy check itself lives in the gateway now, including the reason it
        happens *before* the load: loading for writing calls `resume`, which
        commits crash repair, and a running turn legitimately has a dispatched
        call with no result yet. Resuming underneath it would append a synthetic
        "outcome unknown" for a tool still executing, and the real result would
        land beside it — two answers to one call in an append-only log.
        """
        try:
            run = await web.gateway.receive(
                InboundMessage(channel=web.channel, chat_id=conversation_id, text=body.prompt)
            )
        except SessionNotFoundError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
        except UnknownSkill as err:
            raise _unknown_skill(web, err) from err

        if run is not None:
            return MessageAccepted(**_summary(run.session).model_dump(), queued=False)
        # Queued, so no run came back and the session belongs to the turn already
        # running. Read it live rather than from disk: a flush happens at
        # checkpoints, so disk can be behind on `title`. It can also have settled
        # in the meantime, hence the fallback.
        active = web.runs.active(conversation_id)
        session = (
            active.session
            if active is not None
            else await _load(web.sessions, conversation_id, for_writing=False)
        )
        return MessageAccepted(**_summary(session).model_dump(), queued=True)

    @router.get("/{conversation_id}/events")
    async def stream_events(conversation_id: str, after: int = Query(0, ge=0)) -> StreamingResponse:
        """Events from `after` onward as SSE, live if a turn is running.

        **An idle conversation streams its stored tail, not just `end`.** Without
        that, a turn settling between a client's snapshot and its subscribe would
        leave those events unreachable: the client's cursor says `n`, the log holds
        `n + 5`, and a bare `end` frame would tell it that it was up to date. Serving
        the tail makes the handoff correct however the timing falls.

        **`end` means idle, not "this run settled".** A message sent mid-turn is
        queued and drained into a new run the moment the old one settles; the
        stream waits for that drain and follows the new run at the same cursor,
        so a browser never has to learn about a turn it did not start.

        Closing this response does **not** cancel the run. Nothing here owns the run
        to begin with — the subscription only reads, and `drained` only waits.
        """

        async def source() -> Source:
            run = web.runs.active(conversation_id)
            if run is not None:
                return run
            return await _load(web.sessions, conversation_id, for_writing=False)

        async def after_drain() -> Source:
            # The browser's chat id *is* the conversation id — see `chats.state_of`.
            await web.gateway.drained(web.channel, conversation_id)
            return await source()

        return StreamingResponse(
            sse_frames(await source(), after=after, after_drain=after_drain),
            media_type=MEDIA_TYPE,
            # Buffering a token stream delivers it all at once at the end. This
            # header only covers nginx-shaped proxies; the dev one needs
            # `compress: false` — see frontend/next.config.ts.
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.delete("/{conversation_id}/run", status_code=status.HTTP_204_NO_CONTENT)
    async def stop_run(conversation_id: str) -> Response:
        """Stop the turn in flight. `404` if there is nothing running.

        Returns once the stop is **durable**: `RunStore.stop` awaits settling, so a
        client that got a `204` can re-read the conversation and see the cancelled
        turn rather than racing it.
        """
        if not await web.runs.stop(conversation_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no turn is running")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
