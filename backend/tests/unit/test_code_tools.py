"""The three code-mode tools, against a fake sandbox.

Everything here is about what the *model* sees and what the bridge lets a script
reach. The sandbox itself is real Deno, and lives in
`tests/integration/test_code_mode.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from harness.llm.messages import ToolCall
from harness.sandbox import Bridge, BridgeError, DenoUnavailableError, Runner, Script
from harness.tools.definition import EXECUTION_ERROR, Failure, Ok, ToolDefinition, ToolOutcome
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.native.code import DETAILS, EXECUTE, LIST, code_mode_tools
from harness.tools.registry import ToolRegistry
from tests.unit.helpers import no_progress


def _returns(outcome: Ok):
    async def run(args, progress):
        return outcome

    return run


def tool(name: str, description: str = "A tool.", schema: object | None = None) -> ToolDefinition:
    async def run(args, progress):
        return Ok(f"{name} ran", data={"rows": [1, 2]})

    return ToolDefinition(
        name=name,
        description=description,
        input_schema=schema or {"type": "object", "properties": {"url": {"type": "string"}}},
        parse=lambda raw: raw,
        execute=run,
    )


@dataclass
class FakeRunner(Runner):
    """Stands in for Deno. `script` decides what one run does with the bridge.

    Subclasses `Runner` rather than duck-typing it: a signature that drifts from
    the real runner would otherwise leave these tests passing against a shape
    that no longer exists.
    """

    script: Callable[[Bridge], object] | None = None
    outcome: Script = field(default_factory=lambda: Script(result="ok"))
    unavailable: bool = False
    seen_names: list[str] = field(default_factory=list)
    seen_code: str = ""

    async def run(self, code: str, *, names: Sequence[str], bridge: Bridge) -> Script:
        if self.unavailable:
            raise DenoUnavailableError("no deno here")
        self.seen_names = list(names)
        self.seen_code = code
        if self.script is not None:
            await self.script(bridge)
        return self.outcome


class RecordingDispatcher(ToolDispatcher):
    """A real dispatcher that remembers what it was asked to run.

    A subclass rather than a stand-in callable: `code_mode_tools` takes the
    concrete type, so this is what keeps the fake honest — an override whose
    signature drifts stops compiling against the real one.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        super().__init__(registry)
        self.calls: list[ToolCall] = []

    async def dispatch(self, call: ToolCall, *, progress) -> ToolOutcome:
        self.calls.append(call)
        return await super().dispatch(call, progress=progress)


@dataclass
class Built:
    """The three tools, the registry behind them, and what the dispatcher saw."""

    tools: list[ToolDefinition]
    registry: ToolRegistry
    dispatcher: RecordingDispatcher

    @property
    def dispatched(self) -> list[ToolCall]:
        return self.dispatcher.calls

    def tool(self, name: str) -> ToolDefinition:
        return next(t for t in self.tools if t.name == name)

    async def run(self, name: str, arguments: str = "{}") -> ToolOutcome:
        return await self.tool(name).invoke(arguments, progress=no_progress)


def build(*tools: ToolDefinition, runtime: FakeRunner | None = None) -> Built:
    registry = ToolRegistry(tools)
    dispatcher = RecordingDispatcher(registry)
    built = code_mode_tools(
        registry=registry, dispatcher=dispatcher, runtime=runtime or FakeRunner()
    )
    return Built(tools=built, registry=registry, dispatcher=dispatcher)


# ── what the model is offered ─────────────────────────────────────────────────


def test_exactly_three_tools() -> None:
    assert [t.name for t in build().tools] == [LIST, DETAILS, EXECUTE]


async def test_list_functions_renders_the_catalog_without_types() -> None:
    built = build(tool("yt__get_subtitles", "Fetch subtitles."))

    outcome = await built.run(LIST, "{}")

    assert isinstance(outcome, Ok)
    assert "declare function yt__get_subtitles(args)" in outcome.content
    assert "url" not in outcome.content


async def test_the_catalog_never_contains_code_mode_itself() -> None:
    """The three are registered like any tool so dispatch stays uniform, which
    means they would otherwise list themselves."""
    built = build(tool("yt__a"))
    # The registry is read afresh on every call, so registering the three after
    # the fact is exactly what the composition root does.
    for built_tool in built.tools:
        built.registry.register(built_tool)

    outcome = await built.run(LIST, "{}")

    assert isinstance(outcome, Ok)
    for reserved in (LIST, DETAILS, EXECUTE):
        assert reserved not in outcome.content


async def test_an_empty_catalog_says_so() -> None:
    outcome = await build().run(LIST)

    assert outcome == Ok("No capabilities are available.")


async def test_details_types_the_named_functions_and_notes_the_rest() -> None:
    built = build(tool("yt__a"), tool("yt__b"))

    outcome = await built.run(DETAILS, '{"names": ["yt__a", "ghost"]}')

    assert isinstance(outcome, Ok)
    assert "args: { url?: string }" in outcome.content
    assert "not found: ghost" in outcome.content
    assert "yt__b" not in outcome.content


async def test_details_for_nothing_real_is_ok_not_a_failure() -> None:
    """Wrong names are a rephrase, not a broken tool — a Failure reads to the
    model as "stop using this"."""
    built = build(tool("yt__a"))

    outcome = await built.run(DETAILS, '{"names": ["ghost"]}')

    assert isinstance(outcome, Ok)
    assert LIST in outcome.content


# ── running a script ──────────────────────────────────────────────────────────


async def test_the_script_is_given_every_available_name() -> None:
    runtime = FakeRunner()
    built = build(tool("yt__a"), tool("jobs__b"), runtime=runtime)

    await built.run(EXECUTE, '{"code": "return 1", "description": "d"}')

    assert sorted(runtime.seen_names) == ["jobs__b", "yt__a"]


async def test_logs_and_the_return_value_both_reach_the_model() -> None:
    runtime = FakeRunner(outcome=Script(result={"n": 2}, logs=("first", "second")))
    built = build(runtime=runtime)

    outcome = await built.run(EXECUTE, '{"code": "…", "description": "d"}')

    assert isinstance(outcome, Ok)
    assert "first\nsecond" in outcome.content
    assert '"n": 2' in outcome.content
    assert outcome.data == {"n": 2}


async def test_a_failed_script_keeps_what_it_printed() -> None:
    """A script that threw halfway is debugged from what it printed before it did."""
    runtime = FakeRunner(outcome=Script(logs=("step one done",), error="boom"))
    built = build(runtime=runtime)

    outcome = await built.run(EXECUTE, '{"code": "…", "description": "d"}')

    assert isinstance(outcome, Failure)
    assert outcome.code == EXECUTION_ERROR
    assert "boom" in outcome.message
    assert "step one done" in outcome.message


async def test_a_script_that_returns_nothing_says_so() -> None:
    built = build(runtime=FakeRunner(outcome=Script()))

    outcome = await built.run(EXECUTE, '{"code": "…", "description": "d"}')

    assert isinstance(outcome, Ok)
    assert "without returning" in outcome.content


async def test_a_missing_sandbox_is_reported_as_a_failure_not_a_crash() -> None:
    built = build(runtime=FakeRunner(unavailable=True))

    outcome = await built.run(EXECUTE, '{"code": "…", "description": "d"}')

    assert isinstance(outcome, Failure)
    assert "sandbox could not start" in outcome.message


# ── the bridge ────────────────────────────────────────────────────────────────


async def test_a_call_from_a_script_goes_through_the_ordinary_pipeline() -> None:
    """The whole security and consistency argument: a script reaches exactly what
    the model could, by the same route — and gets a plain value, because the
    sandbox has no idea what a `ToolOutcome` is."""
    seen: list[object] = []

    async def script(bridge: Bridge) -> None:
        seen.append(await bridge("yt__a", {"url": "x"}))

    built = build(tool("yt__a"), runtime=FakeRunner(script=script))

    await built.run(EXECUTE, '{"code": "…", "description": "d"}')

    assert seen == [{"rows": [1, 2]}]
    assert [c.name for c in built.dispatched] == ["yt__a"]


async def test_a_tool_that_publishes_json_as_text_reaches_the_script_as_an_object() -> None:
    """Most MCP servers put JSON in text rather than `structuredContent`. Without
    parsing, a script indexing the result reads `undefined` and the model burns
    turns discovering why — observed live before this existed."""
    seen: list[object] = []

    async def script(bridge: Bridge) -> None:
        seen.append(await bridge("srv__json", {}))

    text_json = tool("srv__json")
    object.__setattr__(text_json, "execute", _returns(Ok('{"jobs": [{"t": "a"}]}')))
    built = build(text_json, runtime=FakeRunner(script=script))

    await built.run(EXECUTE, '{"code": "…", "description": "d"}')

    assert seen == [{"jobs": [{"t": "a"}]}]


async def test_text_that_is_not_json_reaches_the_script_untouched() -> None:
    seen: list[object] = []

    async def script(bridge: Bridge) -> None:
        seen.append(await bridge("srv__prose", {}))

    prose = tool("srv__prose")
    object.__setattr__(prose, "execute", _returns(Ok("2026-09-07T10:31:49+09:00")))
    built = build(prose, runtime=FakeRunner(script=script))

    await built.run(EXECUTE, '{"code": "…", "description": "d"}')

    assert seen == ["2026-09-07T10:31:49+09:00"]


async def test_inner_calls_get_ids_a_provider_could_never_issue() -> None:
    """So a later phase can key nested tool cards on them without ambiguity."""

    async def script(bridge: Bridge) -> None:
        await bridge("yt__a", {})
        await bridge("yt__a", {})

    built = build(tool("yt__a"), runtime=FakeRunner(script=script))

    await built.run(EXECUTE, '{"code": "…", "description": "d"}')

    assert [c.id for c in built.dispatched] == ["sub:1", "sub:2"]


async def test_the_bridge_refuses_code_mode_itself() -> None:
    """Deno never sees these names, so this is the second lock: a script that
    reached one would spawn a sandbox from inside a sandbox, unbounded."""
    raised: list[BridgeError] = []

    async def script(bridge: Bridge) -> None:
        try:
            await bridge(EXECUTE, {"code": "return 1", "description": "d"})
        except BridgeError as err:
            raised.append(err)

    built = build(runtime=FakeRunner(script=script))

    await built.run(EXECUTE, '{"code": "…", "description": "d"}')

    assert "cannot be called from inside a script" in str(raised[0])
    assert built.dispatched == []
