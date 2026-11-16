"""`ask_model` asks the calling bot's model one question about files, with no history."""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from pathlib import Path

from harness.llm import Completion, StreamFailure, ToolCall, UserMessage
from harness.runtime.models import PICK_A_MODEL, NoModel
from harness.tools import EXECUTION_ERROR, INVALID_ARGUMENTS, REFUSED, Failure, Ok, Pending
from harness.tools.native.ask import ASK_MODEL, ask_model_tool
from harness.web.runtime import NOT_CALLABLE_FROM_SCRIPTS, SIGHT_TOOLS
from harness.web.tickets_wiring import WORKER_TOOLS
from tests.unit.fakes import OneModel, ScriptedClient, completed
from tests.unit.helpers import CONVERSATION_ID, ORIGIN, context_for, no_progress
from tests.unit.test_view_image import composed
from tests.webapp import files_in, images_in

ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
INSTRUCTIONS = "List each speech bubble's text as JSON."


class NoModels:
    """A bot with no model picked."""

    async def model_for(self, bot_id: str | None) -> NoModel:
        return NoModel()


async def chunks_of(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def page_in_the_chat(tmp_path: Path, name: str = "page.png", data: bytes = ONE_PIXEL_PNG):
    stored = await files_in(tmp_path).save(CONVERSATION_ID, name, chunks_of(data))
    return Path(stored.path)


def chat_folder(tmp_path: Path) -> Path:
    return files_in(tmp_path).folder(CONVERSATION_ID)


async def asked(
    tmp_path: Path, arguments: dict, client: ScriptedClient, *, vision: bool = True
) -> Ok | Failure:
    tool = ask_model_tool(files_in(tmp_path), images_in(tmp_path), OneModel(client, vision=vision))
    outcome = await tool.invoke(json.dumps(arguments), context=context_for())
    assert isinstance(outcome, Ok | Failure)
    return outcome


async def test_a_json_reply_comes_back_as_an_object_and_as_its_text(tmp_path: Path) -> None:
    page = await page_in_the_chat(tmp_path)
    reply = '```json\n{"bubbles": ["Hi"]}\n```'
    client = ScriptedClient(completed(reply))

    outcome = await asked(tmp_path, {"paths": [str(page)], "instructions": INSTRUCTIONS}, client)

    assert isinstance(outcome, Ok)
    assert outcome.data == {"answer": {"bubbles": ["Hi"]}, "saved_to": None, "usage": None}
    assert outcome.text == '{"bubbles": ["Hi"]}'


async def test_the_model_is_asked_once_with_only_the_instructions_and_the_images(
    tmp_path: Path,
) -> None:
    first = await page_in_the_chat(tmp_path, "1.png")
    second = await page_in_the_chat(tmp_path, "2.png")
    client = ScriptedClient(completed("{}"))

    await asked(tmp_path, {"paths": [str(first), str(second)], "instructions": "Read."}, client)

    assert client.calls == 1
    (message,) = client.seen
    assert isinstance(message, UserMessage)
    assert message.content == "Read."
    assert [image.media_type for image in message.images] == ["image/png", "image/png"]
    assert client.seen_tools is None


async def test_a_reply_that_is_not_json_comes_back_as_text(tmp_path: Path) -> None:
    page = await page_in_the_chat(tmp_path)
    client = ScriptedClient(completed("The page is blank."))

    outcome = await asked(tmp_path, {"paths": [str(page)], "instructions": INSTRUCTIONS}, client)

    assert isinstance(outcome, Ok)
    assert outcome.data == {"answer": "The page is blank.", "saved_to": None, "usage": None}
    assert outcome.text == "The page is blank."


async def test_save_to_writes_the_reply_inside_the_chat_folder(tmp_path: Path) -> None:
    page = await page_in_the_chat(tmp_path)
    target = chat_folder(tmp_path) / "translations" / "page-001.json"
    client = ScriptedClient(completed('```json\n{"n": 1}\n```'))
    arguments = {"paths": [str(page)], "instructions": INSTRUCTIONS, "save_to": str(target)}

    outcome = await asked(tmp_path, arguments, client)

    assert isinstance(outcome, Ok)
    assert target.read_text(encoding="utf-8") == '{"n": 1}'
    assert outcome.data == {"answer": {"n": 1}, "saved_to": str(target), "usage": None}
    assert str(target) in outcome.text
    assert [path.name for path in target.parent.iterdir()] == ["page-001.json"]


async def test_save_to_outside_the_chat_folder_is_refused_before_the_model_is_asked(
    tmp_path: Path,
) -> None:
    page = await page_in_the_chat(tmp_path)
    client = ScriptedClient(completed("{}"))
    escapes = (
        str(tmp_path / "elsewhere.json"),
        str(chat_folder(tmp_path) / ".." / "other-chat.json"),
        str(chat_folder(tmp_path)),
        "answers/page.json",
    )

    for save_to in escapes:
        arguments = {"paths": [str(page)], "instructions": INSTRUCTIONS, "save_to": save_to}
        outcome = await asked(tmp_path, arguments, client)
        assert isinstance(outcome, Failure) and outcome.code == INVALID_ARGUMENTS, save_to

    assert client.calls == 0
    assert not (tmp_path / "elsewhere.json").exists()


async def test_a_path_outside_this_chat_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "secret.png"
    outside.write_bytes(ONE_PIXEL_PNG)
    client = ScriptedClient(completed("{}"))

    outcome = await asked(tmp_path, {"paths": [str(outside)], "instructions": "Read."}, client)

    assert isinstance(outcome, Failure)
    assert outcome.message == f"{outside} is not a file in this chat"
    assert outcome.content[0].text.startswith("error: ")
    assert client.calls == 0


async def test_a_file_that_is_neither_an_image_nor_text_is_refused(tmp_path: Path) -> None:
    named = await page_in_the_chat(tmp_path, "page.gif", b"GIF89a\xff\xfe")
    client = ScriptedClient(completed("{}"))

    outcome = await asked(tmp_path, {"paths": [str(named)], "instructions": "Read."}, client)

    assert outcome == Failure(
        INVALID_ARGUMENTS, f"{named} is neither a PNG or JPEG image nor UTF-8 text"
    )
    assert client.calls == 0


async def test_more_than_twelve_paths_or_blank_instructions_are_refused(
    tmp_path: Path,
) -> None:
    page = await page_in_the_chat(tmp_path)
    client = ScriptedClient(completed("{}"))

    for arguments in (
        {"paths": [str(page)] * 13, "instructions": "Read."},
        {"paths": [str(page)], "instructions": "  "},
    ):
        outcome = await asked(tmp_path, arguments, client)
        assert isinstance(outcome, Failure) and outcome.code == INVALID_ARGUMENTS

    assert client.calls == 0


async def test_a_model_that_cannot_see_is_refused_images_without_a_call(tmp_path: Path) -> None:
    page = await page_in_the_chat(tmp_path)
    client = ScriptedClient(completed("{}"))

    outcome = await asked(
        tmp_path, {"paths": [str(page)], "instructions": "Read."}, client, vision=False
    )

    assert isinstance(outcome, Failure) and outcome.code == REFUSED
    assert client.calls == 0


async def test_a_bot_with_no_model_is_told_to_pick_one(tmp_path: Path) -> None:
    page = await page_in_the_chat(tmp_path)
    tool = ask_model_tool(files_in(tmp_path), images_in(tmp_path), NoModels())

    outcome = await tool.invoke(
        json.dumps({"paths": [str(page)], "instructions": "Read."}), context=context_for()
    )

    assert outcome == Failure(REFUSED, PICK_A_MODEL)


async def test_a_failed_model_call_is_an_error_and_nothing_is_saved(tmp_path: Path) -> None:
    page = await page_in_the_chat(tmp_path)
    target = chat_folder(tmp_path) / "page.json"
    client = ScriptedClient([StreamFailure(reason="provider returned 500: down")])
    arguments = {"paths": [str(page)], "instructions": "Read.", "save_to": str(target)}

    outcome = await asked(tmp_path, arguments, client)

    assert outcome == Failure(EXECUTION_ERROR, "the model call failed: provider returned 500: down")
    assert not target.exists()


async def test_a_stream_with_no_completion_is_an_error(tmp_path: Path) -> None:
    page = await page_in_the_chat(tmp_path)

    outcome = await asked(
        tmp_path, {"paths": [str(page)], "instructions": "Read."}, ScriptedClient([])
    )

    assert outcome == Failure(EXECUTION_ERROR, "the model call ended with no reply")


async def test_the_completion_s_text_is_the_reply(tmp_path: Path) -> None:
    page = await page_in_the_chat(tmp_path)
    client = ScriptedClient([Completion(full_text='{"a": [1, 2]}')])

    outcome = await asked(tmp_path, {"paths": [str(page)], "instructions": "Read."}, client)

    assert isinstance(outcome, Ok) and outcome.data["answer"] == {"a": [1, 2]}


def test_the_description_says_one_call_and_no_history(tmp_path: Path) -> None:
    spec = ask_model_tool(
        files_in(tmp_path), images_in(tmp_path), OneModel(ScriptedClient([]))
    ).spec()

    assert spec.name == ASK_MODEL == "ask_model"
    assert "with no conversation history" in spec.description
    assert "it costs one model call" in spec.description
    assert "Returns {answer, saved_to, usage}" in spec.description
    assert set(spec.input_schema["properties"]) == {"paths", "instructions", "save_to"}
    assert spec.input_schema["required"] == ["instructions"]


def test_workers_are_offered_it_scripts_may_call_it_and_it_needs_no_sight() -> None:
    assert ASK_MODEL in WORKER_TOOLS
    assert ASK_MODEL not in NOT_CALLABLE_FROM_SCRIPTS
    assert ASK_MODEL not in SIGHT_TOOLS


async def test_a_script_s_call_is_dispatched_without_asking_for_approval(tmp_path: Path) -> None:
    runtime = composed(tmp_path)
    page = await page_in_the_chat(tmp_path)
    assert runtime.tools is not None
    call = ToolCall(
        id="sub:1",
        name=ASK_MODEL,
        arguments=json.dumps({"paths": [str(page)], "instructions": "Read."}),
    )

    outcome = await runtime.tools.tool_service.dispatch(
        call, progress=no_progress, approved=False, origin=ORIGIN
    )

    assert not isinstance(outcome, Pending)
    assert outcome == Failure(REFUSED, PICK_A_MODEL)
