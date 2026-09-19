"""`get_location`, declared as a client tool."""

from __future__ import annotations

from pydantic import BaseModel

from harness.tools.client import ClientTool
from harness.tools.native.location.models import Location

LOCATION = "get_location"


class NoArgs(BaseModel):
    """`get_location` takes nothing: the position is the device's to give."""


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
