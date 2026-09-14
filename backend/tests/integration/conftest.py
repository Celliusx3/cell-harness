"""Fixtures shared by the HTTP tests: an app whose model answers at once, and
one whose turn parks inside a tool until something stops it."""

from __future__ import annotations

import pytest

from tests.integration.web_helpers import api, build
from tests.unit.fakes import ScriptedClient, SteppedClient, calls_tool, completed, hanging_tool


@pytest.fixture
async def simple(tmp_path):
    """An app whose model answers in one step."""
    service, runs = build(tmp_path, ScriptedClient(completed("hello")))
    async with api(tmp_path, service, runs) as client:
        yield client, service, runs


@pytest.fixture
async def slow(tmp_path):
    """An app whose turn parks inside a tool until something stops it."""
    service, runs = build(
        tmp_path, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool()
    )
    async with api(tmp_path, service, runs) as client:
        yield client, service, runs
