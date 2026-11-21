"""The workspace tools are offered to every bot and worker, and the memory hook runs for both."""

from __future__ import annotations

from pathlib import Path

from harness.runtime.hooks.native.workspace_memory import WorkspaceMemoryHook
from harness.tools.native.workspace import WORKSPACE_TOOLS
from harness.web.runtime import DEFAULT_TOOLS
from harness.web.tickets_wiring import WORKER_TOOLS
from tests.unit.test_view_image import composed, offered


def test_bots_and_workers_are_offered_the_four_tools() -> None:
    assert WORKSPACE_TOOLS == (
        "workspace_read",
        "workspace_write",
        "workspace_edit",
        "workspace_search",
    )
    assert set(WORKSPACE_TOOLS) <= set(DEFAULT_TOOLS)
    assert set(WORKSPACE_TOOLS) <= set(WORKER_TOOLS)


def test_the_composed_runtime_offers_them_and_shows_the_memory(tmp_path: Path) -> None:
    runtime = composed(tmp_path)

    assert set(WORKSPACE_TOOLS) <= set(offered(runtime, sees_images=False))
    assert any(isinstance(hook, WorkspaceMemoryHook) for hook in runtime.hooks.step_hooks)


def test_no_tool_takes_a_workspace_choice(tmp_path: Path) -> None:
    runtime = composed(tmp_path)
    assert runtime.tools is not None

    for spec in runtime.tools.specs(sees_images=False):
        if spec.name in WORKSPACE_TOOLS:
            assert "workspace" not in spec.input_schema["properties"]
            assert "absolute" in spec.description
