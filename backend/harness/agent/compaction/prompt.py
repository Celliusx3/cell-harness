"""What the summarizer is asked, and what the model reads afterwards."""

from __future__ import annotations

from collections.abc import Sequence

OPEN, CLOSE = "<compacted-summary>", "</compacted-summary>"

PREAMBLE = (
    "This conversation was compacted to free up context. What came before is "
    "summarized below. Treat it as established background: build on it without "
    "restating it, and continue directly from the most recent messages without "
    "mentioning that a compaction happened."
)

_INSTRUCTION_LINES = (
    "You are now acting as a compaction engine for this assistant. Condense the "
    "conversation ABOVE into a structured checkpoint that lets another model "
    "continue it with no loss of essential context.",
    "",
    "Output EXACTLY the Markdown structure below: keep every section, in order. "
    'Use terse bullets, not prose. Write "(none)" for an empty section — never '
    "drop a section.",
    "",
    "## Primary request and intent",
    "- [what the person wanted, originally and as it evolved; quote verbatim "
    "where the exact wording matters]",
    "",
    "## Key facts",
    "- [names, places, addresses, ids, numbers, dates, links and quotes — the "
    "person's or a tool's — exactly as given]",
    "",
    "## Skills loaded",
    "- [each skill the conversation loaded, by name]",
    "",
    "## Tools used and what they returned",
    "- [tool: the result in one line — what was found, not how]",
    "",
    "## Pending",
    "- [explicitly requested work not yet done, and questions the person has not answered]",
    "",
    "## Current work",
    "- [precisely what was in progress at this checkpoint]",
    "",
    "## Next step",
    '- [the single next action, in line with the most recent request, or "(none)"]',
    "",
    "## Critical context",
    "- [decisions and their reasons, the person's preferences and corrections, "
    "constraints, open questions]",
    "",
    "Rules:",
    "- Preserve exact names, identifiers, numbers, addresses, links and quoted "
    "wording. Never invent a detail that is not above.",
    "- Capture the person's corrections and explicit instructions faithfully.",
    "- Do NOT mention this summarization request or that the context was compacted.",
    "- Output only the checkpoint text: do not call any tool or take any other action.",
    f"- If the conversation already contains a {OPEN} block, it is a PRIOR "
    "checkpoint. Do not copy it forward verbatim: keep what is still true, drop "
    "what is stale, and merge newer information into one consolidated checkpoint "
    "with the same structure.",
)

INSTRUCTION = "\n".join(_INSTRUCTION_LINES)


def render(summary: str, skill_bodies: Sequence[str]) -> str:
    """The message the model reads in place of everything before the boundary."""
    parts = [PREAMBLE, f"{OPEN}\n{summary.strip()}\n{CLOSE}", *skill_bodies]
    return "\n\n".join(parts)
