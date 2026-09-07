"""Builders shared across test modules.

Two rules these follow, both inherited from the harness's own test suite:

- **Fake at a seam, never monkeypatch a module.** `ProviderHttp` takes an
  `httpx.AsyncClient`, the pipeline takes a `CommandRunner`, and the media
  backend is a Protocol — so a test constructs the world it wants and nothing
  leaks between tests. A monkeypatched global tests the patch, not the code.
- **No network, no Instagram, no provider.** Everything here is hermetic. The one
  test that talks to the real thing is opt-in and lives in `integration/`.

`fetcher_with` and `reader_with` are separate because the two halves genuinely
are: fetching needs Instagram and no provider, reading needs a provider and no
Instagram. A read test therefore builds no media backend at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from instagram.command import Completed
from instagram.config import Config
from instagram.media.fetch import Fetcher
from instagram.media.sources.fixture import LocalFixtureSource
from instagram.read import Reader
from instagram.read.http import ProviderHttp
from instagram.server import build

FIXTURE_MEDIA = Path(__file__).parent / "fixtures" / "media"


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    return tmp_path / "work"


def make_config(work_dir: Path, **overrides: object) -> Config:
    """A `Config` with everything set, so a test overrides only what it means to.

    Built directly rather than through `load()`: `load` is what validates the
    environment, and it has its own tests. Going through it here would make every
    test depend on ffmpeg being installed.
    """
    values: dict[str, object] = {
        "provider_base_url": "https://provider.test/v1",
        "provider_api_key": "test-key",
        "vision_model": "test-vision",
        "asr_model": "test-asr",
        "media_backend": "fixture",
        "work_dir": work_dir,
        "fixture_root": FIXTURE_MEDIA,
        "ffmpeg": "ffmpeg",
        "ffprobe": "ffprobe",
        "max_frames": 4,
        "max_speech_seconds": 180.0,
        "fetch_concurrency": 4,
        "read_concurrency": 3,
        "call_budget_seconds": 30.0,
        "request_timeout_seconds": 30.0,
    }
    values.update(overrides)
    return Config(**values)  # type: ignore[arg-type]


def http_with(handler) -> ProviderHttp:
    """A `ProviderHttp` whose requests go to `handler` instead of the network."""
    return ProviderHttp(
        base_url="https://provider.test/v1",
        api_key="test-key",
        timeout_seconds=5.0,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def chat_reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def asr_reply(text: str, language: str = "en") -> httpx.Response:
    return httpx.Response(200, json={"text": text, "language": language})


def scripted(routes: dict[str, httpx.Response]):
    """Route by URL suffix, and fail loudly on an unexpected call.

    An unrouted request returning a stub would let a test pass while the code
    called something nobody meant it to.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        for suffix, response in routes.items():
            if request.url.path.endswith(suffix):
                return response
        raise AssertionError(f"unexpected request to {request.url}")

    return handler


def recording_runner(*, code: int = 0, stderr: str = "", touch: str | None = None):
    """A `CommandRunner` that records argv and optionally creates its output.

    Returns `(runner, calls)`. `touch` names a file to create in the directory
    the last argv element points at, so ffmpeg's *effect* can be faked without
    ffmpeg — which is what lets the frame and audio paths be tested hermetically.
    """
    calls: list[list[str]] = []

    async def runner(argv, timeout: float) -> Completed:
        calls.append(list(argv))
        if touch is not None and code == 0:
            target = Path(argv[-1])
            target.parent.mkdir(parents=True, exist_ok=True)
            if "%" in target.name:
                # ffmpeg's numbered-output pattern: make two, as a real sampling
                # of a short clip would.
                for index in (1, 2):
                    (target.parent / (target.name % index)).write_bytes(b"jpegbytes")
            else:
                target.write_bytes(b"audiobytes")
        return Completed(code=code, stdout=b"", stderr=stderr)

    return runner, calls


def fetcher_with(work_dir: Path, runner, *, root: Path | None = None, **overrides: object):
    media_root = root or FIXTURE_MEDIA
    return Fetcher(
        config=make_config(work_dir, fixture_root=media_root, **overrides),
        source=LocalFixtureSource(media_root),
        run=runner,
    )


def reader_with(work_dir: Path, handler, runner, **overrides: object) -> Reader:
    return Reader(config=make_config(work_dir, **overrides), http=http_with(handler), run=runner)


def server_with(work_dir: Path, handler, runner, *, root: Path | None = None, **overrides: object):
    """Both halves wired into a real `MCPServer`."""
    return build(
        fetcher=fetcher_with(work_dir, runner, root=root, **overrides),
        reader=reader_with(work_dir, handler, runner, **overrides),
    )


def write_fixture(root: Path, shortcode: str, meta: dict, *, video: bool = False) -> Path:
    """A media fixture built at runtime, for cases the checked-in set does not cover."""
    directory = root / shortcode
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if video:
        (directory / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return directory
