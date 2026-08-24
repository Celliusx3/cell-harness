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

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from harness.runs.store import RunAlreadyActive, RunStore
from harness.session.log import Session
from harness.session.repository import (
    SessionCorruptionError,
    SessionFormatUnsupportedError,
    SessionNotFoundError,
)
from harness.session.service import SessionService
from harness.web.schemas import ConversationDetail, ConversationSummary, SendMessage
from harness.web.sse import MEDIA_TYPE, sse_frames

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

BUSY = "this conversation is already working on a turn"


def _service(request: Request) -> SessionService:
    return request.app.state.service


def _runs(request: Request) -> RunStore:
    return request.app.state.runs


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


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(request: Request) -> list[ConversationSummary]:
    """Every stored conversation, newest first."""
    return [
        ConversationSummary(id=h.id, created_at=h.created_at, title=h.title)
        for h in await _service(request).list()
    ]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ConversationSummary)
async def create_conversation(request: Request, body: SendMessage) -> ConversationSummary:
    """Start a new conversation with its first message.

    Creating and sending are one call because phase 3's `create()` is lazily
    materialized: it writes nothing, so a bodyless create would hand back an id
    that is absent from the list and gone on refresh. The first message is what
    makes a conversation exist.

    `title` is empty in this response. It is stamped from the first user message
    at the first flush, which happens inside the turn that has only just started —
    so a client shows the text it just sent and lets the next list correct it.
    """
    service = _service(request)
    session = await service.create()
    _runs(request).start(session, body.prompt)
    return _summary(session)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(request: Request, conversation_id: str) -> ConversationDetail:
    """The whole log, and the cursor to start streaming from.

    Reads the **live** session when a turn is running. Going to disk instead would
    return fewer events than the log holds — flushes happen at checkpoints, not
    per event — which is harmless for the cursor but shows a client a conversation
    that is mysteriously behind.
    """
    run = _runs(request).active(conversation_id)
    session = (
        run.session
        if run is not None
        else await _load(_service(request), conversation_id, for_writing=False)
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
    response_model=ConversationSummary,
)
async def send_message(
    request: Request, conversation_id: str, body: SendMessage
) -> ConversationSummary:
    """Continue a conversation. `409` if it is already working.

    **The busy check happens twice, and the first one is not redundant.** Loading
    for writing calls `resume`, which *commits crash repair* — and a running turn
    legitimately has a dispatched call with no result yet. Resuming underneath it
    would append a synthetic "outcome unknown" result for a tool that is still
    executing, and the real result would land beside it: two answers to one call,
    written to an append-only log. So the check before the load prevents
    corruption, and the one after it catches two requests that raced past the
    first.
    """
    runs = _runs(request)
    if runs.active(conversation_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=BUSY)
    session = await _load(_service(request), conversation_id, for_writing=True)
    try:
        runs.start(session, body.prompt)
    except RunAlreadyActive as err:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=BUSY) from err
    return _summary(session)


@router.get("/{conversation_id}/events")
async def stream_events(
    request: Request, conversation_id: str, after: int = Query(0, ge=0)
) -> StreamingResponse:
    """Events from `after` onward as SSE, live if a turn is running.

    **An idle conversation streams its stored tail, not just `end`.** Without
    that, a turn settling between a client's snapshot and its subscribe would
    leave those events unreachable: the client's cursor says `n`, the log holds
    `n + 5`, and a bare `end` frame would tell it that it was up to date. Serving
    the tail makes the handoff correct however the timing falls.

    Closing this response does **not** cancel the run. Nothing here owns the run
    to begin with — the subscription only reads.
    """
    run = _runs(request).active(conversation_id)
    session = (
        run.session
        if run is not None
        else await _load(_service(request), conversation_id, for_writing=False)
    )
    return StreamingResponse(
        sse_frames(run, session, after=after),
        media_type=MEDIA_TYPE,
        # Proxies and browsers buffer by default, which for a token stream means
        # it arrives all at once at the end — the one thing this endpoint exists
        # to avoid.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/{conversation_id}/run", status_code=status.HTTP_204_NO_CONTENT)
async def stop_run(request: Request, conversation_id: str) -> Response:
    """Stop the turn in flight. `404` if there is nothing running.

    Returns once the stop is **durable**: `RunStore.stop` awaits settling, so a
    client that got a `204` can re-read the conversation and see the cancelled
    turn rather than racing it.
    """
    if not await _runs(request).stop(conversation_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no turn is running")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
