"""`ask_model` sends a text file as its text, and needs no sight for it or for no file."""

from __future__ import annotations

from pathlib import Path

from harness.llm import Completion, Usage
from harness.tools import INVALID_ARGUMENTS, Failure, Ok
from harness.tools.native.ask._call import TEXT_MAX_BYTES
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.test_ask_model import asked, page_in_the_chat


async def test_a_text_file_longer_than_the_limit_is_refused(tmp_path: Path) -> None:
    named = await page_in_the_chat(tmp_path, "long.txt", b"a" * (TEXT_MAX_BYTES + 1))
    client = ScriptedClient(completed("{}"))

    outcome = await asked(tmp_path, {"paths": [str(named)], "instructions": "Read."}, client)

    assert isinstance(outcome, Failure) and outcome.code == INVALID_ARGUMENTS
    assert client.calls == 0


async def test_a_text_file_is_sent_after_the_instructions_to_a_model_that_cannot_see(
    tmp_path: Path,
) -> None:
    email = await page_in_the_chat(tmp_path, "email.txt", b"Meet at 3.")
    client = ScriptedClient(completed('{"time": "3"}'))

    outcome = await asked(
        tmp_path, {"paths": [str(email)], "instructions": "When?"}, client, vision=False
    )

    assert isinstance(outcome, Ok) and outcome.data["answer"] == {"time": "3"}
    (message,) = client.seen
    assert message.content == f'When?\n\n<file path="{email}">\nMeet at 3.\n</file>'
    assert message.images == ()


async def test_with_no_paths_only_the_instructions_are_sent(tmp_path: Path) -> None:
    client = ScriptedClient(completed("Paris"))

    outcome = await asked(tmp_path, {"instructions": "Capital of France?"}, client, vision=False)

    assert isinstance(outcome, Ok) and outcome.data["answer"] == "Paris"
    (message,) = client.seen
    assert message.content == "Capital of France?"


async def test_the_call_s_tokens_come_back_with_the_answer(tmp_path: Path) -> None:
    usage = Usage(input_tokens=120, output_tokens=8, cached_input_tokens=0)
    client = ScriptedClient([Completion(full_text="ok", usage=usage)])

    outcome = await asked(tmp_path, {"instructions": "Say ok."}, client)

    assert isinstance(outcome, Ok) and outcome.data["usage"] == usage.model_dump()
