"""Settings: what is required, and what is pinned."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness.config.settings import LLMSettings


@pytest.mark.parametrize("missing", ["api_key", "model"])
def test_required_fields_fail_at_startup(monkeypatch, missing: str) -> None:
    """A default model is a behavioral choice — inheriting one silently is the
    "where did this come from?" bug the house rules forbid."""
    values = {"api_key": "k", "model": "m"}
    del values[missing]
    monkeypatch.delenv(f"HARNESS_LLM_{missing.upper()}", raising=False)

    with pytest.raises(ValidationError):
        LLMSettings(**values)  # type: ignore[arg-type]


def test_reads_the_prefixed_environment(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("HARNESS_LLM_MODEL", "gpt-test")

    settings = LLMSettings()  # type: ignore[call-arg]

    assert settings.api_key == "sk-test"
    assert settings.model == "gpt-test"


def test_temperature_is_pinned_not_inherited() -> None:
    """Left unset it would follow whatever the provider currently defaults to,
    which can change without a line of our code moving."""
    assert LLMSettings(api_key="k", model="m").temperature == 1.0


@pytest.mark.parametrize("bad", [-0.1, 2.1])
def test_temperature_is_bounded(bad: float) -> None:
    with pytest.raises(ValidationError):
        LLMSettings(api_key="k", model="m", temperature=bad)
