"""`ask_model_jobs` answers every call a jobs file lists, each saved where it says."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

from harness.llm import Completion, LLMClient, StreamEvent, StreamFailure, Usage
from harness.tools import INVALID_ARGUMENTS, REFUSED, Failure, Ok
from harness.tools.native.ask import ASK_MODEL_JOBS, ask_model_jobs_tool
from harness.tools.native.ask._call import NO_SIGHT
from harness.web.runtime import SIGHT_TOOLS
from harness.web.tickets_wiring import WORKER_TOOLS
from tests.unit.fakes import OneModel, ScriptedClient, SteppedClient, completed
from tests.unit.helpers import context_for
from tests.unit.test_ask_model import NoModels, chat_folder, page_in_the_chat
from tests.webapp import files_in, images_in


async def jobs_file(tmp_path: Path, jobs: object, name: str = "jobs.json") -> Path:
    path = chat_folder(tmp_path) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jobs), encoding="utf-8")
    return path


async def answered(
    tmp_path: Path, path: Path, client, *, vision: bool = True, at_once: int = 1
) -> Ok | Failure:
    tool = ask_model_jobs_tool(
        files_in(tmp_path), images_in(tmp_path), OneModel(client, vision=vision), at_once=at_once
    )
    outcome = await tool.invoke(json.dumps({"jobs_path": str(path)}), context=context_for())
    assert isinstance(outcome, Ok | Failure)
    return outcome


async def test_each_job_is_asked_once_and_its_reply_saved(tmp_path: Path) -> None:
    first = await page_in_the_chat(tmp_path, "1.png")
    second = await page_in_the_chat(tmp_path, "2.png")
    folder = chat_folder(tmp_path)
    jobs = [
        {"paths": [str(first)], "instructions": "Read 1.", "save_to": str(folder / "a" / "1.json")},
        {
            "paths": [str(second)],
            "instructions": "Read 2.",
            "save_to": str(folder / "a" / "2.json"),
        },
    ]
    client = SteppedClient(completed('{"n": 1}'), completed('```json\n{"n": 2}\n```'))

    outcome = await answered(tmp_path, await jobs_file(tmp_path, jobs), client)

    assert isinstance(outcome, Ok)
    assert outcome.data["answered"] == 2 and outcome.data["failed"] == []
    assert client.calls == 2
    assert [m[0].content for m in client.seen_per_call] == ["Read 1.", "Read 2."]
    assert (folder / "a" / "1.json").read_text() == '{"n": 1}'
    assert (folder / "a" / "2.json").read_text() == '{"n": 2}'


async def test_a_job_that_fails_is_named_and_the_others_still_run(tmp_path: Path) -> None:
    page = await page_in_the_chat(tmp_path)
    folder = chat_folder(tmp_path)
    jobs = [
        {"paths": [str(page)], "instructions": "Read.", "save_to": str(folder / "1.json")},
        {
            "paths": [str(tmp_path / "x.png")],
            "instructions": "R.",
            "save_to": str(folder / "2.json"),
        },
        {"paths": [str(page)], "instructions": "Read.", "save_to": str(folder / "3.json")},
    ]
    client = SteppedClient(completed("{}"), [StreamFailure(reason="down")])

    outcome = await answered(tmp_path, await jobs_file(tmp_path, jobs), client)

    assert isinstance(outcome, Ok)
    assert outcome.data["answered"] == 1
    assert [f["save_to"] for f in outcome.data["failed"]] == [
        str(folder / "2.json"),
        str(folder / "3.json"),
    ]
    assert "not a file in this chat" in outcome.data["failed"][0]["error"]
    assert "down" in outcome.data["failed"][1]["error"]
    assert (folder / "1.json").exists() and not (folder / "3.json").exists()


async def test_a_jobs_file_that_is_not_a_list_of_jobs_is_refused_before_any_call(
    tmp_path: Path,
) -> None:
    page = await page_in_the_chat(tmp_path)
    folder = chat_folder(tmp_path)
    client = ScriptedClient(completed("{}"))
    bad = (
        {"jobs": []},
        [],
        [{"paths": [str(page)], "instructions": "Read."}],
        [{"paths": [str(page)] * 13, "instructions": "Read.", "save_to": str(folder / "1.json")}],
    )

    for index, jobs in enumerate(bad):
        path = await jobs_file(tmp_path, jobs, f"bad-{index}.json")
        outcome = await answered(tmp_path, path, client)
        assert isinstance(outcome, Failure) and outcome.code == INVALID_ARGUMENTS, jobs

    not_json = chat_folder(tmp_path) / "not.json"
    not_json.write_text("not json")
    outcome = await answered(tmp_path, not_json, client)
    assert isinstance(outcome, Failure) and outcome.code == INVALID_ARGUMENTS
    assert client.calls == 0


async def test_a_jobs_file_outside_this_chat_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "jobs.json"
    outside.write_text("[]")

    outcome = await answered(tmp_path, outside, ScriptedClient([]))

    assert isinstance(outcome, Failure) and outcome.code == INVALID_ARGUMENTS


async def test_a_model_that_cannot_see_answers_text_jobs_and_refuses_image_jobs(
    tmp_path: Path,
) -> None:
    page = await page_in_the_chat(tmp_path)
    note = await page_in_the_chat(tmp_path, "note.txt", b"Hello.")
    folder = chat_folder(tmp_path)
    jobs = [
        {"paths": [str(page)], "instructions": "Read.", "save_to": str(folder / "1.json")},
        {"paths": [str(note)], "instructions": "Read.", "save_to": str(folder / "2.json")},
    ]
    client = ScriptedClient(completed("{}"))

    outcome = await answered(tmp_path, await jobs_file(tmp_path, jobs), client, vision=False)

    assert isinstance(outcome, Ok) and outcome.data["answered"] == 1
    assert outcome.data["failed"] == [{"save_to": str(folder / "1.json"), "error": NO_SIGHT}]
    assert client.calls == 1


async def test_a_bot_with_no_model_is_refused_once_without_a_call(tmp_path: Path) -> None:
    save_to = str(chat_folder(tmp_path) / "1.json")
    path = await jobs_file(tmp_path, [{"instructions": "Hi.", "save_to": save_to}])
    tool = ask_model_jobs_tool(files_in(tmp_path), images_in(tmp_path), NoModels(), at_once=1)

    outcome = await tool.invoke(json.dumps({"jobs_path": str(path)}), context=context_for())

    assert isinstance(outcome, Failure) and outcome.code == REFUSED


async def test_the_tokens_of_every_answered_job_are_added_up(tmp_path: Path) -> None:
    folder = chat_folder(tmp_path)
    jobs = [{"instructions": "Hi.", "save_to": str(folder / f"{n}.json")} for n in range(3)]
    client = SteppedClient(
        [Completion(full_text="a", usage=Usage(input_tokens=10, output_tokens=2))],
        [Completion(full_text="b")],
        [
            Completion(
                full_text="c", usage=Usage(input_tokens=5, output_tokens=1, cached_input_tokens=4)
            )
        ],
    )

    outcome = await answered(tmp_path, await jobs_file(tmp_path, jobs), client)

    assert isinstance(outcome, Ok) and outcome.data["answered"] == 3
    assert outcome.data["usage"] == {
        "input_tokens": 15,
        "output_tokens": 3,
        "cached_input_tokens": 4,
    }


def test_the_description_names_the_file_s_shape(tmp_path: Path) -> None:
    spec = ask_model_jobs_tool(
        files_in(tmp_path), images_in(tmp_path), OneModel(ScriptedClient([])), at_once=1
    ).spec()

    assert spec.name == ASK_MODEL_JOBS == "ask_model_jobs"
    assert '"paths", "instructions" and "save_to"' in spec.description
    assert set(spec.input_schema["properties"]) == {"jobs_path"}


def test_workers_are_offered_it_and_it_needs_no_sight() -> None:
    assert ASK_MODEL_JOBS in WORKER_TOOLS
    assert ASK_MODEL_JOBS not in SIGHT_TOOLS


class OverlapClient(LLMClient):
    """Answers each call after a pause, counting how many calls are open at once."""

    def __init__(self) -> None:
        self.open = 0
        self.most_open = 0
        self.calls = 0

    async def stream_completion(self, messages, *, tools=None) -> AsyncIterator[StreamEvent]:
        self.calls += 1
        self.open += 1
        self.most_open = max(self.most_open, self.open)
        await asyncio.sleep(0.02)
        self.open -= 1
        for event in completed("{}"):
            yield event


async def test_jobs_run_at_most_at_once_together(tmp_path: Path) -> None:
    page = await page_in_the_chat(tmp_path)
    folder = chat_folder(tmp_path)
    jobs = [
        {"paths": [str(page)], "instructions": "Read.", "save_to": str(folder / f"{n}.json")}
        for n in range(7)
    ]
    client = OverlapClient()

    outcome = await answered(tmp_path, await jobs_file(tmp_path, jobs), client, at_once=3)

    assert (
        isinstance(outcome, Ok) and outcome.data["answered"] == 7 and outcome.data["failed"] == []
    )
    assert client.calls == 7
    assert client.most_open == 3
    assert sorted(p.name for p in folder.glob("[0-9].json")) == [f"{n}.json" for n in range(7)]
