"""The app ships no MCP server; a settings file that still lists one stops the start."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness.config import settings as settings_module
from harness.config.settings import Settings

BACKEND = Path(__file__).resolve().parents[2]
SHIPPED = (BACKEND / "config.json", BACKEND.parent / "desktop" / "config.json")


@pytest.mark.parametrize("shipped", SHIPPED, ids=["make dev", "Mac app"])
def test_a_shipped_config_declares_no_mcp_server(shipped: Path) -> None:
    committed = json.loads(shipped.read_text())

    assert "servers" not in committed.get("mcp", {})


def test_mcp_servers_left_in_the_local_file_stop_the_start(tmp_path, monkeypatch) -> None:
    committed = tmp_path / "config.json"
    local = tmp_path / "config.local.json"
    committed.write_text("{}")
    local.write_text(json.dumps({"mcp": {"servers": {"computer": {"command": "uv"}}}}))
    monkeypatch.setattr(settings_module, "_CONFIG_JSON", committed)
    monkeypatch.setattr(settings_module, "_LOCAL_JSON", local)

    with pytest.raises(ValidationError, match=r"mcp\.servers\s+Extra inputs are not permitted"):
        Settings()
