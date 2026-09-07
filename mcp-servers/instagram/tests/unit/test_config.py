"""Startup refusals. Each one is a tool the model never sees rather than a tool
that fails every call — which is the whole reason to fail closed here."""

from __future__ import annotations

import pytest

from instagram.config import ConfigError, load

BASE = {
    "AI_PROVIDER_BASE_URL": "https://provider.test/v1",
    "AI_PROVIDER_API_KEY": "k",
    "INSTAGRAM_MEDIA_BACKEND": "instaloader",
}


def test_a_complete_environment_loads() -> None:
    config = load(BASE)

    assert config.media_backend == "instaloader"
    assert config.vision_model == "glm-5.3-flash"


@pytest.mark.parametrize("missing", ["AI_PROVIDER_BASE_URL", "AI_PROVIDER_API_KEY"])
def test_a_missing_credential_refuses_and_names_the_variable(missing: str) -> None:
    """Naming it is the difference between a fixable error and a mystery."""
    env = {k: v for k, v in BASE.items() if k != missing}

    with pytest.raises(ConfigError, match=missing):
        load(env)


def test_an_unknown_backend_refuses_and_lists_the_valid_ones() -> None:
    with pytest.raises(ConfigError, match="instaloader, fixture"):
        load(BASE | {"INSTAGRAM_MEDIA_BACKEND": "yt-dlp"})


def test_the_fixture_backend_requires_a_root() -> None:
    """Selected without one, every fetch would fail identically and confusingly."""
    with pytest.raises(ConfigError, match="INSTAGRAM_FIXTURE_ROOT"):
        load(BASE | {"INSTAGRAM_MEDIA_BACKEND": "fixture"})


def test_a_missing_ffmpeg_refuses_at_startup_not_at_the_first_read() -> None:
    """ffmpeg cannot be a pip dependency, so unlike instaloader it is a PATH
    requirement — and one that must be checked before the server binds."""
    with pytest.raises(ConfigError, match="not on PATH"):
        load(BASE | {"INSTAGRAM_FFMPEG": "definitely-not-a-real-binary-xyz"})


@pytest.mark.parametrize(
    ("name", "value", "because"),
    [
        ("INSTAGRAM_MAX_FRAMES", "0", "greater than zero"),
        ("INSTAGRAM_MAX_FRAMES", "-3", "greater than zero"),
        ("INSTAGRAM_MAX_FRAMES", "many", "not an integer"),
        ("INSTAGRAM_CALL_BUDGET_SECONDS", "0", "greater than zero"),
        ("INSTAGRAM_CALL_BUDGET_SECONDS", "soon", "not a number"),
    ],
)
def test_an_unusable_number_refuses_rather_than_silently_defaulting(
    name: str, value: str, because: str
) -> None:
    with pytest.raises(ConfigError, match=because):
        load(BASE | {name: value})


def test_a_blank_value_takes_the_default_rather_than_refusing() -> None:
    """An env var set to empty is how a shell passes "unset", and refusing it
    would make an ordinary config file unusable."""
    assert load(BASE | {"INSTAGRAM_MAX_FRAMES": ""}).max_frames == 8


def test_the_work_dir_is_expanded_so_a_tilde_is_not_a_literal_directory() -> None:
    config = load(BASE | {"INSTAGRAM_WORK_DIR": "~/somewhere"})

    assert "~" not in str(config.work_dir)
