"""The chat shows a lead's reply without its `<goal>` block, run through the frontend's own code."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_CONVERSATION = Path(__file__).resolve().parents[3] / "frontend" / "components" / "conversation"
_GOAL_BLOCK_TS = _CONVERSATION / "goalBlock.ts"

pytestmark = pytest.mark.skipif(shutil.which("deno") is None, reason="deno is not installed")


def _shown(texts: list[str]) -> list[str]:
    script = (
        f"import {{ withoutGoalBlocks }} from {json.dumps(_GOAL_BLOCK_TS.as_uri())};\n"
        f"console.log(JSON.stringify({json.dumps(texts)}.map(withoutGoalBlocks)));"
    )
    ran = subprocess.run(
        ["deno", "eval", "--ext=ts", script], capture_output=True, text=True, check=True
    )
    return json.loads(ran.stdout)


def test_the_block_is_hidden_and_the_words_before_it_are_kept() -> None:
    texts = [
        'Over to Writer.\n<goal>{"status":"continue","next":"Writer","task":"Draft"}</goal>',
        'An example <goal>{"status":"done"}</goal> and the real one <goal>{}</goal>',
        'Still arriving <goal>{"status":"cont',
        "No block here.",
    ]

    assert _shown(texts) == [
        "Over to Writer.",
        "An example  and the real one",
        "Still arriving",
        "No block here.",
    ]
