"""The two tools through a real MCP client, in-process.

**This module holds the single most important test in this server**:
`test_the_result_arrives_as_structured_content_a_script_can_index`. The harness's
`mcp/tool.py` `outcome_of` sets `Ok(data=result.structured_content)`, and its
code-mode bridge hands that to the model's program as a JavaScript object. The
harness's own `docs/mcp-tool-scaling.md` §6 records what happens when a server
publishes JSON as text instead: *"a script reading `results.jobs` got
`undefined`. Observed live: five failing scripts and a cancelled turn."*

Everything here is hermetic — a fixture media backend and a mocked provider.
"""

from __future__ import annotations

from pathlib import Path

from mcp import Client

from tests.unit.tools_helpers import call, server_for

# --- the contract ---------------------------------------------------------


async def test_the_result_arrives_as_structured_content_a_script_can_index(
    work_dir: Path,
) -> None:
    """Proves the `Ok(data=...)` path the harness's code mode depends on.

    If this returns None, the model's program reads `undefined` and burns turns
    writing scripts against a shape that is not there.
    """
    result = await call(
        server_for(work_dir),
        "fetch_reels",
        {"urls": ["https://www.instagram.com/reel/OKvideo000/"]},
    )

    assert result.structured_content is not None
    items = result.structured_content["items"]
    assert items[0]["status"] == "ok"
    assert items[0]["shortcode"] == "OKvideo000"


async def test_both_tools_are_offered_with_an_output_schema(work_dir: Path) -> None:
    """The `output_schema` is what makes `structuredContent` happen at all."""
    async with Client(server_for(work_dir)) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert set(tools) == {"fetch_reels", "read_reels"}
    assert tools["fetch_reels"].output_schema is not None
    assert tools["read_reels"].output_schema is not None


# --- fetch ----------------------------------------------------------------


async def test_a_caption_and_its_mentions_come_back_whole(work_dir: Path) -> None:
    """The caption is the highest-yield POI signal and is never truncated."""
    result = await call(
        server_for(work_dir), "fetch_reels", {"urls": ["https://www.instagram.com/p/OKvideo000/"]}
    )

    item = result.structured_content["items"][0]
    assert item["caption"] == "Best nasi lemak in Bangsar 📍 @warung.mak.cik #nasilemak"
    assert item["mentions"] == ["warung.mak.cik"]
    assert item["tagged_users"] == ["kldirectory"]
    assert item["media"] == "video"
    assert item["backend"] == "fixture"


async def test_the_url_is_echoed_so_results_join_back_to_inputs(work_dir: Path) -> None:
    url = "https://www.instagram.com/reel/OKvideo000/?stkn=abc"

    result = await call(server_for(work_dir), "fetch_reels", {"urls": [url]})

    assert result.structured_content["items"][0]["url"] == url


async def test_an_image_only_post_reports_image_not_a_failure(work_dir: Path) -> None:
    result = await call(server_for(work_dir), "fetch_reels", {"urls": ["OKimage000"]})

    item = result.structured_content["items"][0]
    assert (item["status"], item["media"]) == ("ok", "image")


async def test_one_bad_url_never_sinks_the_others(work_dir: Path) -> None:
    """A tool failure would reach the script as a thrown Error and destroy every
    sibling result — so per-item problems are statuses, not failures."""
    result = await call(
        server_for(work_dir),
        "fetch_reels",
        {
            "urls": [
                "https://www.instagram.com/reel/OKvideo000/",
                "https://youtube.com/watch?v=x",
                "https://www.instagram.com/reel/GONE000000/",
                "https://www.instagram.com/reel/SLOW000000/",
            ]
        },
    )

    items = result.structured_content["items"]
    assert [item["status"] for item in items] == [
        "ok",
        "unsupported_url",
        "unavailable",
        "rate_limited",
    ]
    # Order is positional, so a caller can zip results back onto its input list.
    assert items[0]["shortcode"] == "OKvideo000"


async def test_a_rate_limit_carries_its_retry_hint(work_dir: Path) -> None:
    result = await call(server_for(work_dir), "fetch_reels", {"urls": ["SLOW000000"]})

    assert result.structured_content["items"][0]["retry_after_seconds"] == 30


async def test_an_unavailable_reel_explains_itself_in_a_sentence(work_dir: Path) -> None:
    result = await call(server_for(work_dir), "fetch_reels", {"urls": ["GONE000000"]})

    item = result.structured_content["items"][0]
    assert "private" in item["detail"]
    assert item["caption"] == ""
