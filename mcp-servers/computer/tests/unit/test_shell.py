"""shell through a real MCP client: started detached once, waited on, and answered once."""

from __future__ import annotations

import json
import re

import pytest
from mcp import Client
from mcp.types import CallToolResult, TextContent

from computer.jobs import RUNNER_SCRIPT, WRITE_SCRIPT
from computer.machine import HOME, JOBS_ROOT
from computer.shell import ENDED_UNREPORTED
from computer.tools.descriptions import COMMAND_DESCRIPTION, CWD_DESCRIPTION, STDIN_DESCRIPTION
from tests.conftest import NAME, server_with
from tests.job_docker import JobDocker

QUOTED = 'it\'s "here" $HOME'
SLOW = 100


def text_of(result: CallToolResult) -> str:
    return "".join(block.text for block in result.content if isinstance(block, TextContent))


async def calls(docker: JobDocker, *arguments: dict[str, object]) -> list[CallToolResult]:
    async with Client(server_with(docker)) as client:
        return [await client.call_tool("shell", args) for args in arguments]


async def answers(docker: JobDocker, *arguments: dict[str, object]) -> list[dict[str, object]]:
    results = await calls(docker, *arguments)
    assert not any(result.is_error for result in results), [text_of(r) for r in results]
    return [result.structured_content or {} for result in results]


async def test_a_quick_command_answers_done_with_its_exit_code_and_output() -> None:
    docker = JobDocker()
    docker.exit_code = 3

    (result,) = await calls(docker, {"command": "echo hi; exit 3"})

    done = {"status": "done", "exit_code": 3, "seconds": 0.5, "output": "hi\n"}
    assert result.structured_content == done
    assert json.loads(text_of(result)) == done


async def test_the_command_and_its_input_go_on_stdin_and_never_in_an_argument() -> None:
    docker = JobDocker()
    command = "python3 -c 'import sys; print(sys.stdin.read())'"

    await answers(docker, {"command": command, "stdin": QUOTED})

    sent = zip(docker.calls, docker.stdins, strict=True)
    (written,) = [stdin for call, stdin in sent if WRITE_SCRIPT in call]
    assert json.loads(written) == {"command": command, "stdin": QUOTED, "cwd": HOME}
    assert not [arg for call in docker.calls for arg in call if command in arg or QUOTED in arg]


async def test_the_runner_is_launched_detached_in_the_home_folder() -> None:
    docker = JobDocker()

    await answers(docker, {"command": "ls"})

    (launch,) = docker.runner_calls()
    *start, folder, cwd = launch
    assert start == ["exec", "-d", NAME, "sh", "-c", RUNNER_SCRIPT, "shell-job"]
    assert re.fullmatch(rf"{JOBS_ROOT}/[0-9a-f]{{16}}", folder)
    assert cwd == HOME


async def test_a_folder_given_is_where_it_runs_and_makes_another_job() -> None:
    docker = JobDocker()

    await answers(docker, {"command": "ls"}, {"command": "ls", "cwd": "/tmp"})

    home, tmp = docker.runner_calls()
    assert tmp[-1] == "/tmp"
    assert home[-2] != tmp[-2]


async def test_a_slow_command_answers_running_with_seconds_that_grow() -> None:
    docker = JobDocker(looks_to_finish=SLOW)
    slow = {"command": "sleep 60"}

    first, second = await answers(docker, slow, slow)

    assert (first["status"], first["exit_code"]) == ("running", None)
    assert (second["status"], second["exit_code"]) == ("running", None)
    assert 0 < first["seconds"] < second["seconds"]


async def test_calling_again_attaches_to_the_running_job_without_launching_it_again() -> None:
    docker = JobDocker(looks_to_finish=SLOW)
    slow = {"command": "sleep 60"}

    steps = await answers(docker, slow, slow, slow, slow)

    assert [step["status"] for step in steps] == ["running", "running", "running", "done"]
    assert len(docker.runner_calls()) == 1


async def test_a_finished_result_comes_once_then_the_same_call_runs_it_again() -> None:
    docker = JobDocker()
    quick = {"command": "date"}

    first, second = await answers(docker, quick, quick)

    assert first["status"] == second["status"] == "done"
    assert len(docker.runner_calls()) == 2


@pytest.mark.parametrize(("looks", "status"), [(1, "done"), (SLOW, "running")])
async def test_a_long_output_keeps_its_end(looks: int, status: str) -> None:
    docker = JobDocker(looks_to_finish=looks)
    docker.output = "".join(f"line {number}\n" for number in range(5000))

    (answer,) = await answers(docker, {"command": "seq 5000"})

    assert answer["status"] == status
    assert answer["output"] == docker.output[-10_000:]
    assert str(answer["output"]).endswith("line 4999\n")


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"command": ""},
        {"command": "ls", "cwd": "tmp"},
        {"command": "ls", "cwd": ""},
        {"command": "ls", "cwd": "/a\x00b"},
    ],
)
async def test_arguments_that_do_not_fit_are_refused_before_any_docker_call(
    args: dict[str, object],
) -> None:
    docker = JobDocker()
    async with Client(server_with(docker)) as client:
        at_startup = list(docker.calls)
        result = await client.call_tool("shell", args)

    assert result.is_error
    assert docker.calls == at_startup


async def test_the_schema_describes_each_argument_and_publishes_the_result() -> None:
    async with Client(server_with(JobDocker())) as client:
        (tool,) = [tool for tool in (await client.list_tools()).tools if tool.name == "shell"]

    properties = tool.input_schema["properties"]
    command, stdin, cwd = properties["command"], properties["stdin"], properties["cwd"]
    assert (command["description"], command["minLength"]) == (COMMAND_DESCRIPTION, 1)
    assert (stdin["description"], stdin["default"]) == (STDIN_DESCRIPTION, "")
    assert (cwd["description"], cwd["default"]) == (CWD_DESCRIPTION, None)
    assert tool.input_schema["required"] == ["command"]
    assert tool.output_schema is not None
    assert set(tool.output_schema["properties"]) == {"status", "exit_code", "seconds", "output"}


async def test_a_job_that_ends_without_an_exit_code_says_to_run_it_again() -> None:
    docker = JobDocker()
    docker.runner_dies = True

    (result,) = await calls(docker, {"command": "ls"})

    assert result.is_error
    assert text_of(result).endswith(ENDED_UNREPORTED)


@pytest.mark.parametrize("answer", ["not json", '{"state": "done"}', '{"state": "lost"}'])
async def test_an_answer_this_server_cannot_read_is_an_error(answer: str) -> None:
    docker = JobDocker()
    docker.look_answer = answer

    (result,) = await calls(docker, {"command": "ls"})

    assert result.is_error
    assert "cannot read" in text_of(result)


async def test_a_refused_exec_reaches_the_model_in_the_computers_words() -> None:
    docker = JobDocker()
    docker.refused_verbs.add("exec")

    (result,) = await calls(docker, {"command": "ls"})

    assert result.is_error
    assert text_of(result).endswith("Looking at the command failed: Error: exec refused")


async def test_docker_unreachable_reaches_the_model_as_the_computer_not_available() -> None:
    docker = JobDocker()
    async with Client(server_with(docker)) as client:
        docker.unreachable = True
        result = await client.call_tool("shell", {"command": "ls"})

    assert result.is_error
    assert "The computer is not available: docker is not on PATH" in text_of(result)


async def test_a_stopped_computer_is_started_for_a_command() -> None:
    docker = JobDocker(status="exited")

    await answers(docker, {"command": "ls"})

    assert ["start", NAME] in docker.calls
    assert docker.verbs().index("start") < docker.calls.index(docker.runner_calls()[0])


async def test_a_command_runs_while_the_person_holds_the_screen() -> None:
    docker = JobDocker()
    async with Client(server_with(docker)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        result = await client.call_tool("shell", {"command": "ls"})

    assert not result.is_error, text_of(result)
