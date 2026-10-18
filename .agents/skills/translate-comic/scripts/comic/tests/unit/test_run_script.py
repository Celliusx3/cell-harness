"""run.py asks `uv run --script` for the project's own Python and runtime dependencies."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

SCRIPTS = Path(__file__).parents[3]
METADATA = re.compile(r"(?m)^# /// script$\s(?P<content>(^#(| .*)$\s)+)^# ///$")


def test_the_scripts_inline_metadata_matches_the_project() -> None:
    found = METADATA.search((SCRIPTS / "run.py").read_text())
    assert found is not None
    content = "".join(
        line[2:] if line.startswith("# ") else line[1:]
        for line in found["content"].splitlines(keepends=True)
    )
    project = tomllib.loads((SCRIPTS / "pyproject.toml").read_text())["project"]

    assert tomllib.loads(content) == {
        "requires-python": project["requires-python"],
        "dependencies": project["dependencies"],
    }
