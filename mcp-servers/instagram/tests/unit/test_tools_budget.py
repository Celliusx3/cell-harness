"""The per-call budget over a batch."""

from __future__ import annotations

import asyncio

import pytest

from instagram.tools.budget import with_budget


async def test_work_that_fits_all_completes_in_caller_order() -> None:
    async def work(key: int) -> str:
        await asyncio.sleep(0)
        return f"done-{key}"

    out = await with_budget(
        [1, 2, 3], work, seconds=5, concurrency=2, on_timeout=lambda k: f"late-{k}"
    )

    assert out == ["done-1", "done-2", "done-3"]


async def test_finished_items_survive_when_others_run_out_of_budget() -> None:

    async def work(key: int) -> str:
        await asyncio.sleep(0.01 if key == 1 else 5)
        return f"done-{key}"

    out = await with_budget(
        [1, 2], work, seconds=0.2, concurrency=2, on_timeout=lambda k: f"late-{k}"
    )

    assert out == ["done-1", "late-2"]


async def test_items_that_never_started_are_reported_late_not_hung() -> None:

    async def work(key: int) -> str:
        await asyncio.sleep(5)
        return f"done-{key}"

    out = await with_budget(
        [1, 2], work, seconds=0.1, concurrency=1, on_timeout=lambda k: f"late-{k}"
    )

    assert out == ["late-1", "late-2"]


async def test_no_keys_is_no_work_and_no_error() -> None:
    async def work(key: int) -> str:
        raise AssertionError("should not run")

    assert await with_budget([], work, seconds=1, concurrency=1, on_timeout=lambda k: "x") == []


async def test_a_real_exception_still_propagates() -> None:

    async def work(key: int) -> str:
        raise ValueError("a genuine bug")

    with pytest.raises(ValueError, match="a genuine bug"):
        await with_budget([1], work, seconds=1, concurrency=1, on_timeout=lambda k: "x")
