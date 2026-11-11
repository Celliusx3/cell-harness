"""The screen read as elements: a recorded `uiautomator` dump turned into one line each."""

from __future__ import annotations

import pytest

from phone.models.command import CommandResult
from phone.services.elements import (
    DUMP,
    DUMP_TIMEOUT_SECONDS,
    NOTHING_ON_SCREEN,
    Elements,
    ElementsError,
    elements_text,
)
from tests.fakes import NAME, FakeEngine

HEAD = "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"


def dump_of(*nodes: str) -> str:
    return f'{HEAD}<hierarchy rotation="0">{"".join(nodes)}</hierarchy>'


def node(
    text: str = "",
    desc: str = "",
    rid: str = "",
    clickable: str = "false",
    bounds: str = "[0,0][10,10]",
) -> str:
    return (
        f'<node text="{text}" content-desc="{desc}" resource-id="{rid}" '
        f'clickable="{clickable}" bounds="{bounds}" />'
    )


def test_each_element_is_its_words_id_clickable_and_centre() -> None:
    dump = dump_of(
        node(text="¥12.90", rid="com.x:id/price", clickable="true", bounds="[10,600][351,641]"),
        node(text="Buy", desc="Buy now", bounds="[0,0][100,50]"),
        node(desc="Share"),
    )

    assert elements_text(dump) == (
        '- text "¥12.90", id com.x:id/price, clickable, center (180, 620)\n'
        '- text "Buy", description "Buy now", center (50, 25)\n'
        '- description "Share", center (5, 5)'
    )


def test_nested_elements_are_all_read() -> None:
    dump = dump_of(f'<node text="" content-desc="" bounds="[0,0][9,9]">{node(text="In")}</node>')

    assert elements_text(dump) == '- text "In", center (5, 5)'


def test_a_screen_with_no_words_or_descriptions_says_so() -> None:
    assert elements_text(dump_of(node(rid="com.x:id/spacer"))) == NOTHING_ON_SCREEN


@pytest.mark.parametrize("bounds", ["", "[0,0]", "[a,b][c,d]", "[0,0][1,1]x"])
def test_bounds_it_cannot_read_are_refused(bounds: str) -> None:
    with pytest.raises(ElementsError, match="bounds it cannot read"):
        elements_text(dump_of(node(text="x", bounds=bounds)))


@pytest.mark.parametrize(
    ("dump", "said"),
    [
        (f'{HEAD}<!DOCTYPE x [<!ENTITY a "b">]><hierarchy/>', "DOCTYPE"),
        ("ERROR: could not get idle state.", "not XML"),
        (f"{HEAD}<html/>", "not a hierarchy"),
    ],
)
def test_a_dump_that_is_not_a_plain_hierarchy_is_refused(dump: str, said: str) -> None:
    with pytest.raises(ElementsError, match=said):
        elements_text(dump)


async def test_the_dump_runs_with_a_longer_timeout() -> None:
    engine = FakeEngine(state="running", answers={DUMP.argv[1]: CommandResult(0, dump_of(), "")})

    assert await Elements(engine=engine, name=NAME).listed() == NOTHING_ON_SCREEN
    assert engine.commands == [DUMP.argv[1]]
    assert engine.timeouts == [DUMP_TIMEOUT_SECONDS]


async def test_a_dump_android_refuses_fails_in_its_words() -> None:
    engine = FakeEngine(state="running", answers={DUMP.argv[1]: CommandResult(1, "", "no ui\n")})

    with pytest.raises(ElementsError, match="Reading the screen failed: no ui"):
        await Elements(engine=engine, name=NAME).listed()
