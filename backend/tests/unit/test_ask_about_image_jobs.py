"""`ask_about_image_jobs` answers every call a jobs file lists, each saved where it says."""

from __future__ import annotations

import json
from pathlib import Path

from harness.llm import StreamFailure
from harness.tools import INVALID_ARGUMENTS, REFUSED, Failure, Ok
from harness.tools.native.files import ASK_ABOUT_IMAGE_JOBS, ask_about_image_jobs_tool
from harness.web.runtime import SIGHT_TOOLS
from harness.web.tickets_wiring import WORKER_TOOLS
from tests.unit.fakes import OneModel, ScriptedClient, SteppedClient, completed
from tests.unit.helpers import context_for
from tests.unit.test_ask_about_images import chat_folder, page_in_the_chat
from tests.webapp import files_in, images_in


async def jobs_file(tmp_path: Path, jobs: object, name: str = "jobs.json") -> Path:
    path = chat_folder(tmp_path) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jobs), encoding="utf-8")
    return path


async def answered(tmp_path: Path, path: Path, client, *, vision: bool = True) -> Ok | Failure:
    tool = ask_about_image_jobs_tool(
        files_in(tmp_path), images_in(tmp_path), OneModel(client, vision=vision)
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
    assert outcome.data == {"answered": 2, "failed": []}
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
        [{"paths": [], "instructions": "Read.", "save_to": str(folder / "1.json")}],
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


async def test_a_model_that_cannot_see_is_refused_once_without_a_call(tmp_path: Path) -> None:
    page = await page_in_the_chat(tmp_path)
    save_to = str(chat_folder(tmp_path) / "1.json")
    jobs = [{"paths": [str(page)], "instructions": "Read.", "save_to": save_to}] * 3
    client = ScriptedClient(completed("{}"))

    outcome = await answered(tmp_path, await jobs_file(tmp_path, jobs), client, vision=False)

    assert isinstance(outcome, Failure) and outcome.code == REFUSED
    assert client.calls == 0


def test_the_description_names_the_file_s_shape(tmp_path: Path) -> None:
    spec = ask_about_image_jobs_tool(
        files_in(tmp_path), images_in(tmp_path), OneModel(ScriptedClient([]))
    ).spec()

    assert spec.name == ASK_ABOUT_IMAGE_JOBS == "ask_about_image_jobs"
    assert '"paths", "instructions" and "save_to"' in spec.description
    assert set(spec.input_schema["properties"]) == {"jobs_path"}


def test_workers_are_offered_it_and_it_needs_sight() -> None:
    assert ASK_ABOUT_IMAGE_JOBS in WORKER_TOOLS
    assert ASK_ABOUT_IMAGE_JOBS in SIGHT_TOOLS
