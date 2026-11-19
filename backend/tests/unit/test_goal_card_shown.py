"""A goal run's start and end become its line and card, run through the frontend's code."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_CONVERSATION = Path(__file__).resolve().parents[3] / "frontend" / "components" / "conversation"
_GOAL_RUN_TS = _CONVERSATION / "goalRun.ts"

pytestmark = pytest.mark.skipif(shutil.which("deno") is None, reason="deno is not installed")

_EVENTS = [
    {"type": "bot/instructions", "name": "Researcher", "instructions": "", "bot_id": "r1"},
    {"type": "goal/start", "turn": 1, "goal": "Plan the launch", "lead_id": "r1", "max_turns": 13},
    {"type": "goal/step", "turn": 1, "bot_id": "r1", "role": "lead", "step": 1},
    {
        "type": "goal/end",
        "turn": 3,
        "status": "stopped",
        "detail": "Stopped by you.",
        "turns_used": 2,
    },
]


def _run(expression: str) -> object:
    script = (
        f"import {{ GOAL_STATUS_WORDS, goalItems }} from {json.dumps(_GOAL_RUN_TS.as_uri())};\n"
        f"const events = {json.dumps(_EVENTS)};\n"
        f"console.log(JSON.stringify({expression}));"
    )
    ran = subprocess.run(
        ["deno", "eval", "--ext=ts", script], capture_output=True, text=True, check=True
    )
    return json.loads(ran.stdout)


def test_a_goal_start_and_end_map_to_the_line_and_the_card() -> None:
    assert _run("[...goalItems(events)]") == [
        [1, {"kind": "goalStart", "key": "gs1", "goal": "Plan the launch", "lead": "Researcher"}],
        [
            3,
            {
                "kind": "goalEnd",
                "key": "ge3",
                "goal": "Plan the launch",
                "lead": "Researcher",
                "turnsUsed": 2,
                "maxTurns": 13,
                "status": "stopped",
                "detail": "Stopped by you.",
            },
        ],
    ]


def test_every_status_has_its_words() -> None:
    assert _run("GOAL_STATUS_WORDS") == {
        "done": "Done",
        "needs_you": "Needs you",
        "blocked": "Blocked",
        "limit_reached": "Turn limit reached",
        "stopped": "Stopped",
        "failed": "Failed",
    }
