"""What the two tools return."""

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
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    tagged_users: list[str] = Field(default_factory=list)
    posted_at: str | None = Field(default=None, description="ISO 8601, UTC.")
    retry_after_seconds: float | None = None
    backend: str = Field(default="", description="Which media backend answered.")


class FetchReels(BaseModel):
    """The `fetch_reels` result."""

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
    notes: list[str] = Field(default_factory=list)


class ReadReels(BaseModel):
    items: list[ReadReel]
