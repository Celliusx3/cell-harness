"""`hand_over`, declared as a client tool."""

from __future__ import annotations

from harness.tools.client import ClientTool
from harness.tools.native.hand_over.models import HandOver, HandOverAnswer

HAND_OVER = "hand_over"

HAND_OVER_TOOL = ClientTool(
    name=HAND_OVER,
    description=(
        "Ask the user to do one step on the computer that only they should do: a password, "
        "a two-factor code, a captcha, a payment or a passkey. Call it when the page in the "
        "computer's Chrome needs that step; never ask for a password or a code in chat. The "
        "turn waits while they open the computer, take control, do it, and press I'm done or "
        'Skip. The result is {"finished": true} when they pressed I\'m done: call '
        "computer__browser_read_page before anything else, carry on from where you stopped, "
        'and do not hand the same step over again. {"finished": false} means they skipped '
        "it: carry on without treating that step as done, and do not hand it over again "
        "unless you still cannot go on."
    ),
    args_model=HandOver,
    data_model=HandOverAnswer,
)
