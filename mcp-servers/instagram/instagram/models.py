"""What the two tools return.

These are pydantic models rather than dicts for one concrete reason, recorded in
the harness's own `docs/mcp-tool-scaling.md` §6: *"Most MCP servers publish JSON
as text rather than `structuredContent`, so a script reading `results.jobs` got
`undefined`. Observed live: five failing scripts and a cancelled turn."* Returning
a model makes the MCP server emit an `outputSchema` and populate
`structuredContent`, which the harness passes through as `Ok.data` — a real
indexable object in the model's program.

**Per-item `status`, never a per-item failure.** A tool `Failure` becomes a thrown
`Error` inside the sandbox and takes every sibling result with it, so one private
reel would sink nine good ones. Anything true of *one item* is an `Ok` with a
status; only facts about the whole call may fail.

No `location_tag` field. Instagram's location sticker is login-gated and we are
deliberately anonymous, so the field would always be empty — and a field that is
always empty is a fact the model will reason from wrongly. `tagged_users` carries
the corroborating signal instead.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FetchStatus = Literal["ok", "unavailable", "rate_limited", "unsupported_url", "error"]
ReadStatus = Literal["ok", "partial", "timeout", "not_fetched", "error"]
MediaKind = Literal["video", "image", "none"]
SpeechState = Literal["present", "none", "skipped", "unavailable", "failed"]


class FetchedReel(BaseModel):
    """One reel's text metadata, and whether its media is in hand."""

    url: str = Field(description="The URL as given, so a caller can join results back to inputs.")
    shortcode: str = Field(description="The only key read_reels accepts. Empty when unparseable.")
    status: FetchStatus
    detail: str = Field(default="", description="A sentence when not ok; empty when ok.")
    media: MediaKind = "none"
    duration_seconds: float | None = None
    author: str = ""
    # Never truncated. The house rule is explicit that rendering handles
    # overflow, and the caption is the single highest-yield POI signal there is —
    # in a live test it was the *only* one, carrying "📍 Rajgad Fort" on a reel
    # with no mentions, no hashtags and no location.
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    tagged_users: list[str] = Field(default_factory=list)
    posted_at: str | None = Field(default=None, description="ISO 8601, UTC.")
    retry_after_seconds: float | None = None
    backend: str = Field(default="", description="Which media backend answered.")


class FetchReels(BaseModel):
    """Wrapped in a named field because `structuredContent` must be an object.

    Left bare, the server would wrap it for us under a generic key; naming it
    `items` means the model's program reads `r.items` rather than guessing.
    """

    items: list[FetchedReel]


class ReadReel(BaseModel):
    """What one reel shows and says."""

    shortcode: str
    status: ReadStatus
    detail: str = ""
    overlay_text: list[str] = Field(
        default_factory=list,
        description="Deduplicated on-screen text, reading order.",
    )
    scene: str = Field(default="", description="What the frames depict, as prose.")
    frames_read: int = 0
    sampled_over_seconds: float = 0.0
    transcript: str = ""
    speech: SpeechState = "skipped"
    speech_seconds: float = 0.0
    language: str = ""
    # Situational caveats only — "transcribed the first 180s of 600", "no legible
    # overlay in 12 frames". The *constant* caveat (that transcripts mangle local
    # proper nouns) belongs in the tool description, not repeated on every item
    # where it would read as noise and get skimmed.
    notes: list[str] = Field(default_factory=list)


class ReadReels(BaseModel):
    items: list[ReadReel]
