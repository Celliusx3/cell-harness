"""`/name args` — a person loads a skill, so the model does not have to decide.

The spec calls this user invocation: "the harness handles the lookup and
injection, so the model receives skill content without needing to take an
activation action itself." Every chat client has it (`/name` in Claude Code
and OpenClaw, `$name` in Codex and Hermes), and none logs it as a second
message type — the user message *is* the expansion. This one is Claude Code's
shape: what was typed, then the skill exactly as the `skill` tool would have
returned it. One string, logged whole, so a skill edited next week does not
rewrite this week's conversation.

**The typed line comes first, and that order is the contract.** It is what
lets the title and the timeline recover the short form with no extra field:
everything before the first `MARKER` is what the person wrote. The typed text
may span lines and the skill may append a bundled-files line; neither moves the
split, because it is on the *opening* tag, once. The one ambiguity is a person
deliberately typing `MARKER` into an ordinary message — their bubble would then
show only what precedes it. Accepted rather than guarded: the marker is a tag
nobody types, and a guard would have to escape the person's words.

`SkillService.expand` builds the string; `frontend/lib/invocation.ts` mirrors
`display`; a test pins the two markers.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from harness.skills.models import valid_name

# Where the person's words end and the skill begins. The tag is the one the
# `skill` tool already uses, so the model sees one shape for both surfaces.
MARKER = '\n\n<skill name="'


class Display(BaseModel):
    """The short form of an invoked message: which skill, and what was typed."""

    model_config = ConfigDict(frozen=True)

    skill: str
    typed: str


def parse(text: str) -> str | None:
    """The skill name a message starts with, or `None` for ordinary text.

    Only the first word counts, and only when it is `/` plus a valid skill
    name — `/usr/bin/x` is a path and `hello /name` is prose. One invocation
    per message; stacking is a feature nobody has asked for.
    """
    first, _, _ = text.lstrip().partition(" ")
    first = first.split("\n", 1)[0]
    if not first.startswith("/"):
        return None
    name = first[1:]
    return name if valid_name(name) else None


def display(content: str) -> Display | None:
    """The typed line and skill name back out of an expanded message, or
    `None` when the message is not one."""
    typed, marker, rest = content.partition(MARKER)
    if not marker:
        return None
    skill, quote, _ = rest.partition('"')
    if not quote or not valid_name(skill):
        return None
    return Display(skill=skill, typed=typed)
