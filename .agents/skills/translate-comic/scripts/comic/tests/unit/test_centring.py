"""Each text layer is moved so its extent sits centred on its letter box, across and down."""

from __future__ import annotations

from comic.chapter.pages import Box
from comic.chapter.plan import Plan
from comic.document import BatchStep
from comic.lettering.text_layers import Bounds, Line, TextLayer, TypeInfo, _centring_steps

LETTER = Box(600, 1300, 40, 160)
PLAN = Plan(english="Good luck", text=LETTER, erase=LETTER, fill=LETTER, px=28, smallest=28)


def measured_layer(bounds: Bounds) -> TextLayer:
    info = TypeInfo(lines=[Line(start=0, end=9)], bounds=bounds, pxPerPt=1.0)
    return TextLayer(PLAN, LETTER, layer=7, px=28, info=info)


def test_text_wider_than_its_box_is_moved_back_over_the_box_centre() -> None:
    [step] = _centring_steps([measured_layer(Bounds(left=610, top=1340, right=690, bottom=1400))])

    assert step == BatchStep(command="type.edit", params={"layer": 7, "move": [-30, 10]})


def test_text_already_centred_is_not_moved() -> None:
    [step] = _centring_steps([measured_layer(Bounds(left=605, top=1350, right=635, bottom=1410))])

    assert step.params == {"layer": 7, "move": [0, 0]}
