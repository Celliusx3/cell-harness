"""The two tools through a real MCP client, in-process."""

from __future__ import annotations

from pathlib import Path

from mcp import Client

from tests.unit.tools_helpers import call, server_for


async def test_the_result_arrives_as_structured_content_a_script_can_index(
    work_dir: Path,
) -> None:
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
    async with Client(server_for(work_dir)) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert set(tools) == {"fetch_reels", "read_reels"}
    assert tools["fetch_reels"].output_schema is not None
    assert tools["read_reels"].output_schema is not None


async def test_a_caption_and_its_mentions_come_back_whole(work_dir: Path) -> None:
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
    assert items[0]["shortcode"] == "OKvideo000"


async def test_a_rate_limit_carries_its_retry_hint(work_dir: Path) -> None:
    result = await call(server_for(work_dir), "fetch_reels", {"urls": ["SLOW000000"]})

    assert result.structured_content["items"][0]["retry_after_seconds"] == 30


async def test_an_unavailable_reel_explains_itself_in_a_sentence(work_dir: Path) -> None:
    result = await call(server_for(work_dir), "fetch_reels", {"urls": ["GONE000000"]})

    item = result.structured_content["items"][0]
    assert "private" in item["detail"]
    assert item["caption"] == ""
