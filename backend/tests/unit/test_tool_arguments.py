"""What `invoke` says when the model's arguments do not fit the schema."""

from __future__ import annotations

from harness.llm.messages import ToolCall
from harness.tools.definition import (
    INVALID_ARGUMENTS,
    Failure,
    Ok,
    ToolDefinition,
    ToolOutcome,
)
from harness.tools.pipeline import ToolPipeline
from harness.tools.progress import ToolProgressReporter
from tests.unit.helpers import no_progress, pipeline_for


def pipeline(*tools: ToolDefinition) -> ToolPipeline:
    return pipeline_for(*tools)


def call(name: str, arguments: str) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments)


def profile_tool() -> ToolDefinition[dict]:
    """An MCP-shaped tool: a hand-written schema and an identity parser."""

    async def execute(args: dict, progress: ToolProgressReporter) -> ToolOutcome:
        return Ok(content=f"profile of {args['id']}")

    return ToolDefinition(
        name="profile",
        description="A company profile.",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "string"}, "kind": {"type": "string"}},
            "required": ["id"],
        },
        parse=lambda raw: raw,
        execute=execute,
    )


async def test_missing_required_fields_say_what_was_sent_and_what_is_expected() -> None:
    outcome = await pipeline(profile_tool()).execute(
        call("profile", '{"kind": "stock"}'), progress=no_progress
    )

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS
    assert "missing required field id" in outcome.message
    assert "You sent: kind" in outcome.message
    assert "Expected fields: id (required), kind" in outcome.message


async def test_arguments_wrapped_in_args_are_a_missing_field_not_a_server_error() -> None:
    outcome = await pipeline(profile_tool()).execute(
        call("profile", '{"args": {"id": "AAPL"}}'), progress=no_progress
    )

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS
    assert "missing required field id" in outcome.message
    assert "You sent: args" in outcome.message


async def test_extra_keys_with_every_required_field_pass_through() -> None:
    outcome = await pipeline(profile_tool()).execute(
        call("profile", '{"id": "AAPL", "extra": 1}'), progress=no_progress
    )

    assert isinstance(outcome, Ok)
    assert outcome.text == "profile of AAPL"


async def test_a_schema_without_required_fields_is_not_checked() -> None:
    tool = profile_tool()
    loose = ToolDefinition(
        name="loose",
        description=tool.description,
        input_schema={"type": "object", "properties": {"id": {"type": "string"}}},
        parse=tool.parse,
        execute=tool.execute,
    )

    outcome = await pipeline(loose).execute(call("loose", '{"other": 1}'), progress=no_progress)

    assert not (isinstance(outcome, Failure) and outcome.code == INVALID_ARGUMENTS)
