"""URL normalization — every shape Instagram's share sheet actually produces."""

from __future__ import annotations

import pytest

from instagram.reel import NotAReelUrl, parse

CODE = "C6NiA4lRux8"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.instagram.com/reel/{CODE}/",
        f"https://www.instagram.com/reels/{CODE}/",
        f"https://www.instagram.com/p/{CODE}/",
        f"https://www.instagram.com/tv/{CODE}/",
        f"https://instagram.com/reel/{CODE}/",
        f"https://m.instagram.com/reel/{CODE}/",
        f"https://www.instagram.com/kl.foodie/reel/{CODE}/",
        f"https://www.instagram.com/reel/{CODE}",
        f"www.instagram.com/reel/{CODE}/",
    ],
)
def test_every_post_url_shape_yields_the_same_shortcode(url: str) -> None:
    assert parse(url).shortcode == CODE


@pytest.mark.parametrize(
    "param",
    [
        "igsh=MzRlODBiNWFlZA==",
        "stkn=bjk1bHFvZXg0MGV4",
        "utm_source=ig_web_copy_link",
        "img_index=1",
    ],
)
def test_share_tracking_parameters_are_dropped(param: str) -> None:
    assert parse(f"https://www.instagram.com/reel/{CODE}/?{param}").shortcode == CODE


def test_the_url_is_kept_verbatim_so_a_caller_can_join_results_to_inputs() -> None:
    url = f"https://www.instagram.com/reel/{CODE}/?stkn=abc"

    assert parse(url).url == url


def test_a_bare_shortcode_is_accepted_because_read_reels_speaks_them() -> None:
    ref = parse(CODE)

    assert (ref.shortcode, ref.url) == (CODE, CODE)


def test_a_share_redirect_link_is_refused_by_name_not_silently_mis_parsed() -> None:
    with pytest.raises(NotAReelUrl) as caught:
        parse("https://www.instagram.com/share/reel/_AbCdEf12/")

    message = str(caught.value)
    assert "share-redirect" in message
    assert "instagram.com/reel/<code>/" in message


@pytest.mark.parametrize(
    ("url", "because"),
    [
        ("https://youtube.com/watch?v=x", "not an instagram.com URL"),
        ("https://www.instagram.com.evil.example/reel/abc/", "not an instagram.com URL"),
        ("https://www.instagram.com/kl.foodie/", "does not name a single post"),
        ("https://www.instagram.com/explore/tags/nasilemak/", "does not name a single post"),
        ("", "no URL was given"),
    ],
)
def test_anything_that_is_not_a_single_post_is_refused_with_a_reason(
    url: str, because: str
) -> None:
    with pytest.raises(NotAReelUrl, match=because):
        parse(url)
