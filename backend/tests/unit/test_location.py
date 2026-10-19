"""`get_location` — the datum and the declaration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness.tools.client import ClientToolCatalog, ClientToolService
from harness.tools.native.location import GET_LOCATION, GET_LOCATION_TOOL, Location
from tests.unit.helpers import no_approvals


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
    (tool,) = ClientToolService(ClientToolCatalog((GET_LOCATION_TOOL,)), no_approvals()).tools()
    spec = tool.spec()
    assert spec.name == GET_LOCATION
    assert spec.input_schema.get("properties", {}) == {}
    assert "near me" in spec.description
