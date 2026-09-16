"""The three code-mode tools, against a fake sandbox.

Everything here is about what the *model* sees and what the bridge lets a script
reach. The sandbox itself is real Deno, and lives in
`tests/integration/test_code_mode.py`.
"""

from __future__ import annotations

from harness.sandbox import Bridge, BridgeError, Script
from harness.tools.definition import EXECUTION_ERROR, Failure, Ok
from harness.tools.native.code import DETAILS, EXECUTE, LIST
from tests.unit.code_fakes import FakeRunner, build, returns, tool


async def test_a_withheld_tool_is_unlisted_unbound_and_refused() -> None:
    """The composition root's list of tools a script may not reach, checked at
    all three locks: the catalog, the sandbox globals, and the bridge."""
    raised: list[BridgeError] = []

    async def script(bridge: Bridge) -> None:
        try:
            await bridge("skill", {"name": "x"})
        except BridgeError as err:
            raised.append(err)

    runtime = FakeRunner(script=script)
    built = build(tool("skill"), tool("yt__a"), runtime=runtime, withheld=frozenset({"skill"}))

    listed = await built.run(LIST, "{}")
    assert isinstance(listed, Ok) and "skill" not in listed.text

    await built.run(EXECUTE, '{"code": "…", "description": "d"}')
    assert runtime.seen_names == ["yt__a"]
    assert "cannot be called from inside a script" in str(raised[0])
    assert built.dispatched == []


# ── what the model is offered ─────────────────────────────────────────────────


def test_exactly_three_tools() -> None:
    assert [t.name for t in build().tools] == [LIST, DETAILS, EXECUTE]


async def test_list_functions_renders_the_catalog_without_types() -> None:
    built = build(tool("yt__get_subtitles", "Fetch subtitles."))

    outcome = await built.run(LIST, "{}")

    assert isinstance(outcome, Ok)
    assert "declare function yt__get_subtitles(args)" in outcome.text
    assert "url" not in outcome.text


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
        assert reserved not in outcome.text


async def test_an_empty_catalog_says_so() -> None:
    outcome = await build().run(LIST)

    assert outcome == Ok("No capabilities are available.")


async def test_details_types_the_named_functions_and_notes_the_rest() -> None:
    built = build(tool("yt__a"), tool("yt__b"))

    outcome = await built.run(DETAILS, '{"names": ["yt__a", "ghost"]}')

    assert isinstance(outcome, Ok)
    assert "args: { url?: string }" in outcome.text
    assert "not found: ghost" in outcome.text
    assert "yt__b" not in outcome.text


async def test_details_for_nothing_real_is_ok_not_a_failure() -> None:
    """Wrong names are a rephrase, not a broken tool — a Failure reads to the
    model as "stop using this"."""
    built = build(tool("yt__a"))

    outcome = await built.run(DETAILS, '{"names": ["ghost"]}')

    assert isinstance(outcome, Ok)
    assert LIST in outcome.text


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
    assert "first\nsecond" in outcome.text
    assert '"n": 2' in outcome.text
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
    assert "nothing came back" in outcome.text
    assert "no data has been fetched" in outcome.text


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
    object.__setattr__(text_json, "execute", returns(Ok('{"jobs": [{"t": "a"}]}')))
    built = build(text_json, runtime=FakeRunner(script=script))

    await built.run(EXECUTE, '{"code": "…", "description": "d"}')

    assert seen == [{"jobs": [{"t": "a"}]}]


async def test_text_that_is_not_json_reaches_the_script_untouched() -> None:
    seen: list[object] = []

    async def script(bridge: Bridge) -> None:
        seen.append(await bridge("srv__prose", {}))

    prose = tool("srv__prose")
    object.__setattr__(prose, "execute", returns(Ok("2026-09-07T10:31:49+09:00")))
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
