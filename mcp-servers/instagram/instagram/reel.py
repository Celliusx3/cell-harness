"""A shared Instagram URL to the one key everything else uses: the shortcode.

Instagram's share sheet does not emit one URL shape, it emits several, and the
library we hand the result to takes a **shortcode, not a URL**. So this is a
required first step rather than tidying.

Every shape below was tested against a live extractor; the two surprises are
recorded as tests in `tests/unit/test_reel.py`:

- `/share/reel/<id>/` is a *redirect wrapper*, not a shortcode. Its id is not the
  post's id, so guessing it through would fetch the wrong thing or nothing.
- `?igsh=` / `?stkn=` / `?utm_source=` tracking params ride along on real shares
  and must come off before the path is read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

# `/reels/` (plural) is a real shape the web app produces; `/tv/` is the retired
# IGTV prefix that still resolves. `/<username>/reel/<code>/` is what search
# results and the mobile app hand you, so the leading segment is optional and
# discarded — the shortcode is unique on its own.
_SHORTCODE = re.compile(
    r"^/(?:[A-Za-z0-9._]+/)?(?:reel|reels|p|tv)/(?P<code>[A-Za-z0-9_-]+)/?$",
)

# Matched only to give a *specific* refusal. Without it these fall into the
# generic "not an Instagram post URL", which tells the user to check a URL that
# is in fact the one Instagram gave them.
_SHARE_WRAPPER = re.compile(r"^/share/(?:reel/|p/)?[A-Za-z0-9_-]+/?$")

_HOSTS = frozenset({"instagram.com", "www.instagram.com", "m.instagram.com"})


@dataclass(frozen=True)
class ReelRef:
    """One reel, addressed both ways.

    `url` is kept verbatim rather than reconstructed so the model can join a
    result back to the input it supplied — including the tracking params, which
    are noise to us but are what the user pasted.
    """

    url: str
    shortcode: str


class NotAReelUrl(ValueError):
    """The input is not a URL naming a single Instagram post.

    Carries a sentence for the model, not a code: the only useful recovery is
    telling the person which link to send instead.
    """


def parse(url: str) -> ReelRef:
    """`url` to a `ReelRef`, or raise `NotAReelUrl` saying why.

    Deliberately total on the happy shapes and loud on everything else. Silently
    returning something for `/share/` links would be the worst outcome: they
    parse fine as text and name a post that does not exist.
    """
    text = url.strip()
    if not text:
        raise NotAReelUrl("no URL was given")

    # Bare shortcodes are accepted because `read_reels` speaks them, and a model
    # that has one in hand should not have to rebuild a URL to re-fetch.
    if "/" not in text and "." not in text and _is_shortcode(text):
        return ReelRef(url=text, shortcode=text)

    split = urlsplit(text if "//" in text else f"https://{text}")
    if split.hostname is None or split.hostname.lower() not in _HOSTS:
        raise NotAReelUrl(f"not an instagram.com URL: {url!r}")

    path = split.path if split.path.startswith("/") else f"/{split.path}"

    # Checked BEFORE the shortcode pattern, and this order is load-bearing: the
    # optional `<username>/` segment happily matches `share/`, so `/share/reel/X/`
    # would otherwise parse as owner "share" with `X` as a shortcode — the exact
    # silent mis-parse this refusal exists to prevent. Caught by
    # `test_a_share_redirect_link_is_refused_by_name_not_silently_mis_parsed`.
    if _SHARE_WRAPPER.match(path):
        # Resolving this needs an HTTP redirect follow, which belongs to the
        # media backend, not to string parsing. Saying so is more useful than a
        # generic refusal, because the fix is a different link the user can get.
        raise NotAReelUrl(
            f"{url!r} is an Instagram share-redirect link, which does not contain the post's "
            "shortcode. Open it and copy the link from the post itself, or send the "
            "instagram.com/reel/<code>/ form."
        )

    if match := _SHORTCODE.match(path):
        return ReelRef(url=url, shortcode=match["code"])

    raise NotAReelUrl(
        f"{url!r} is an Instagram URL but does not name a single post — expected "
        "instagram.com/reel/<code>/ or instagram.com/p/<code>/"
    )


def _is_shortcode(text: str) -> bool:
    """Shortcodes are base64url and, in practice, 10-12 characters.

    The bound is deliberately loose: Instagram has lengthened them before, and
    refusing a valid new-format code would break fetching entirely, where
    accepting a wrong one merely fails the lookup with a clear message.
    """
    return 8 <= len(text) <= 24 and re.fullmatch(r"[A-Za-z0-9_-]+", text) is not None
