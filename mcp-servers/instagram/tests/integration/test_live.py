"""The one test that touches the real Instagram and the real provider."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from instagram.command import run_command
from instagram.media.fetch import Fetcher
from instagram.media.sources.instaloader import InstaloaderSource
from instagram.read import Reader
from instagram.read.http import ProviderHttp
from instagram.reel import parse
from instagram.server import build

DEFAULT_REEL = "https://www.instagram.com/reel/C6NiA4lRux8/"

LIVE_REEL = os.environ.get("INSTAGRAM_LIVE_REEL", "").strip() or DEFAULT_REEL

pytestmark = pytest.mark.skipif(
    os.getenv("INSTAGRAM_LIVE") != "1", reason="set INSTAGRAM_LIVE=1 to hit the real services"
)


async def test_a_real_public_reel_fetches_with_no_credentials(tmp_path: Path) -> None:
    media = await InstaloaderSource().fetch(parse(LIVE_REEL), tmp_path / "media")

    assert media.caption, "a real reel has a caption"
    assert media.author
    assert media.video is not None
    assert media.video.stat().st_size > 100_000


async def test_the_whole_chain_produces_readable_observations(tmp_path: Path) -> None:
    key = os.environ.get("AI_PROVIDER_API_KEY", "")
    if not key:
        pytest.skip("AI_PROVIDER_API_KEY is required for the live provider")

    from tests.conftest import make_config

    http = ProviderHttp(
        base_url=os.environ.get("AI_PROVIDER_BASE_URL", "https://api.ilmu.ai/v1"),
        api_key=key,
        timeout_seconds=180.0,
    )
    config = make_config(
        tmp_path / "work",
        media_backend="instaloader",
        fixture_root=None,
        vision_model=os.environ.get("AI_VISION_MODEL", "glm-5.3-flash"),
        asr_model=os.environ.get("AI_ASR_MODEL", "ilmu-asr-v4.2"),
        call_budget_seconds=240.0,
        request_timeout_seconds=180.0,
    )
    server = build(
        fetcher=Fetcher(
            config=config, source=InstaloaderSource(timeout_seconds=180.0), run=run_command
        ),
        reader=Reader(config=config, http=http, run=run_command),
    )

    from mcp import Client

    async with Client(server) as client:
        fetched = await client.call_tool("fetch_reels", {"urls": [LIVE_REEL]})
        item = fetched.structured_content["items"][0]
        print(f"\ncaption: {item['caption'][:200]}")
        print(f"mentions: {item['mentions']}  tagged: {item['tagged_users']}")
        assert item["status"] == "ok"

        read = await client.call_tool(
            "read_reels",
            {"shortcodes": [item["shortcode"]], "want": ["visual", "speech"]},
        )

    observed = read.structured_content["items"][0]
    print(f"overlay: {observed['overlay_text']}")
    print(f"scene: {observed['scene'][:300]}")
    print(f"speech={observed['speech']} transcript: {observed['transcript'][:200]}")
    print(f"notes: {observed['notes']}")

    assert observed["status"] in {"ok", "partial"}
    assert observed["frames_read"] > 0
    await http.aclose()
