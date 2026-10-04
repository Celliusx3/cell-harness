"""The system message's text: a conversation's logged bot instructions, then the agent's own."""

from __future__ import annotations

from harness.session.log import Session


def system_text(session: Session, guidance: str) -> str:
    """The instructions `session` logged last, then `guidance`; `guidance` alone when none are."""
    logged = session.bot_instructions()
    if logged is None:
        return guidance
    if not guidance:
        return logged.instructions
    return f"{logged.instructions} {guidance}"
