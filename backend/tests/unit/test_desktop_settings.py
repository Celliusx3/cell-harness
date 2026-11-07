"""The desktop app's settings: its own file pair, with every data path in the app's folder."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
DESKTOP_CONFIG = BACKEND.parent / "desktop" / "config.json"
APP_FOLDER = Path("Library") / "Application Support" / "Cell Harness"

_PRINT_LOADED = """
import json
import sys
from pathlib import Path
from harness.config.settings import Settings
s = Settings(local_settings_path=Path(sys.argv[1]))
print(json.dumps({
    "api_key": s.llm.api_key,
    "servers": list(s.mcp.servers),
    "data_paths": [str(p) for p in (
        s.sessions.root, s.skills.editable, s.approval.grants_path,
        s.bots.path, s.secrets.path, s.files.root,
    )],
}))
"""


@dataclass(frozen=True)
class Loaded:
    api_key: str
    servers: list[str]
    data_paths: list[str]


def _load_as_the_app(home: Path, local: Path) -> Loaded:
    env = {name: value for name, value in os.environ.items() if not name.startswith("HARNESS_")}
    env |= {
        "HOME": str(home),
        "HARNESS_CONFIG": str(DESKTOP_CONFIG),
        "HARNESS_CONFIG_LOCAL": str(local),
    }
    result = subprocess.run(
        [sys.executable, "-c", _PRINT_LOADED, str(local)],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return Loaded(**json.loads(result.stdout))


def test_the_app_reads_its_local_file_from_the_path_it_names(tmp_path) -> None:
    local = tmp_path / "elsewhere" / "config.local.json"
    local.parent.mkdir()
    local.write_text(json.dumps({"llm": {"api_key": "sk-from-the-app"}}))

    loaded = _load_as_the_app(tmp_path / "home", local)

    assert loaded.api_key == "sk-from-the-app"


def test_the_app_has_every_capability_make_dev_has_but_the_computer(tmp_path) -> None:
    loaded = _load_as_the_app(tmp_path / "home", tmp_path / "missing.json")

    dev_servers = json.loads((BACKEND / "config.json").read_text())["mcp"]["servers"]
    assert sorted(loaded.servers) == sorted(set(dev_servers) - {"computer"})


def test_each_capability_waits_for_the_keys_it_waits_for_in_make_dev() -> None:
    app = json.loads(DESKTOP_CONFIG.read_text())["mcp"]["servers"]
    dev = json.loads((BACKEND / "config.json").read_text())["mcp"]["servers"]

    assert {name: server.get("needs", []) for name, server in app.items()} == {
        name: dev[name].get("needs", []) for name in app
    }


def test_every_capability_keeps_its_data_in_the_app_folder() -> None:
    servers = json.loads(DESKTOP_CONFIG.read_text())["mcp"]["servers"]

    folders = [
        setting
        for server in servers.values()
        for name, setting in server.get("env", {}).items()
        if name.endswith(("_HOME", "_DIR"))
    ]

    assert folders
    assert all(folder.startswith(f"~/{APP_FOLDER}/") for folder in folders), folders


def test_every_data_path_is_in_the_app_folder(tmp_path) -> None:
    home = tmp_path / "home"

    loaded = _load_as_the_app(home, tmp_path / "missing.json")

    folder = home / APP_FOLDER
    assert all(Path(path).is_relative_to(folder) for path in loaded.data_paths), loaded.data_paths
