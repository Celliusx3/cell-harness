"""What the summarizer is asked, and what the model reads afterwards.

Prompt text is code. The instruction is dsh's structured checkpoint reshaped
for a chat product: a coding harness keeps file paths and error strings; this
one keeps the names, places, ids, numbers and links a person gave or a tool
returned, because that is what the next turn asks about. The preamble is
Claude Code's "continued from a previous conversation" line.

The instruction is a list joined by newlines rather than one triple-quoted
string only so each source line stays legible and under the width cap; the
model receives one block of Markdown either way.
"""

from __future__ import annotations

from collections.abc import Sequence

OPEN, CLOSE = "<compacted-summary>", "</compacted-summary>"

PREAMBLE = (
    "This conversation was compacted to free up context. What came before is "
    "summarized below. Treat it as established background: build on it without "
    "restating it, and continue directly from the most recent messages without "
    "mentioning that a compaction happened."
)

# "Do NOT mention": a model that sees a summarization request in its history
# will otherwise open its next reply with "as summarized above". "Output only
# the checkpoint": tools are not offered on this request, but a model that
# writes `execute_typescript(` in prose is still a summary that cannot be used.
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


def render(summary: str, skills: Sequence[tuple[str, str]]) -> str:
    """The message the model reads in place of everything before the boundary:
    the preamble, the summary in its tags, then every skill body still in
    force — Claude Code re-attaches the last invocation of each skill."""
    parts = [PREAMBLE, f"{OPEN}\n{summary.strip()}\n{CLOSE}"]
    parts.extend(body for _, body in skills)
    return "\n\n".join(parts)
