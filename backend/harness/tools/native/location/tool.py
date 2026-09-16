"""The declaration."""

from __future__ import annotations

from pydantic import BaseModel

from harness.tools.client import ClientTool
from harness.tools.native.location.models import Location

LOCATION = "get_location"


class NoArgs(BaseModel):
    """`get_location` takes nothing: the position is the device's to give."""


# The trigger words are the point: a model not told when to reach for this
# answers "I don't know where you are" instead of asking. "Read the catalog"
# is there because, told only to "pass the coordinates to a places search", a
# model wrote a script calling `places__search` — a name it guessed — and
# reported the failure as the answer (2026-09-16).
LOCATION_TOOL = ClientTool(
    name=LOCATION,
    description=(
        "The user's current position, from their device. Call this when they say "
        "'near me', 'nearby', 'around here', or ask for directions from where they "
        "are. Then find a places search with list_functions and pass it the "
        "latitude and longitude — never guess a function name. The user is asked "
        "to share and may refuse — then ask them for a place or city instead."
    ),
    args_model=NoArgs,
    data_model=Location,
)
