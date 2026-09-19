"""`get_location` — the datum and the declaration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness.tools.client import ClientTools, ClientToolService
from harness.tools.native.location import LOCATION, LOCATION_TOOL, Location


def test_coordinates_are_bounded_and_nothing_extra_is_accepted() -> None:
    with pytest.raises(ValidationError):
        Location(latitude=91.0, longitude=0.0, accuracy_m=1.0)
    with pytest.raises(ValidationError):
        Location(latitude=0.0, longitude=181.0, accuracy_m=1.0)
    with pytest.raises(ValidationError):
        Location(latitude=0.0, longitude=0.0, accuracy_m=-1.0)
    with pytest.raises(ValidationError):
        Location(latitude=0.0, longitude=0.0, accuracy_m=1.0, altitude=3.0)


def test_the_tool_takes_no_arguments_and_names_its_trigger_words() -> None:
    (tool,) = ClientToolService(ClientTools((LOCATION_TOOL,))).definitions()
    spec = tool.spec()
    assert spec.name == LOCATION
    assert spec.input_schema.get("properties", {}) == {}
    assert "near me" in spec.description
