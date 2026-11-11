"""Startup refusals, and the shared name the phone runs under by default."""

from __future__ import annotations

from pathlib import Path

import pytest

from phone.config import ConfigError, load

IMAGE = "ghcr.io/celliusx3/cell-harness/phone@sha256:" + "1" * 64


def settings(tmp_path: Path) -> dict[str, str]:
    kernel = tmp_path / "libkrunfw.5.dylib"
    kernel.write_bytes(b"\x00")
    return {"PHONE_IMAGE": IMAGE, "PHONE_KERNEL": str(kernel)}


def test_the_image_and_kernel_set_load_under_the_shared_name(tmp_path: Path) -> None:
    config = load(settings(tmp_path))

    assert (config.image, config.name, config.kernel) == (
        IMAGE,
        "cell-harness-phone",
        (tmp_path / "libkrunfw.5.dylib").resolve(),
    )


def test_the_name_can_be_overridden(tmp_path: Path) -> None:
    assert load({**settings(tmp_path), "PHONE_NAME": "cell-harness-phone-test"}).name == (
        "cell-harness-phone-test"
    )


@pytest.mark.parametrize("variable", ["PHONE_IMAGE", "PHONE_KERNEL"])
def test_a_required_setting_left_out_is_refused_by_name(tmp_path: Path, variable: str) -> None:
    env = {**settings(tmp_path), variable: "  "}

    with pytest.raises(ConfigError, match=f"{variable} is not set"):
        load(env)


@pytest.mark.parametrize("name", ["x", "-phone", "my phone", "phone/1"])
def test_a_name_microsandbox_would_not_take_is_refused(tmp_path: Path, name: str) -> None:
    with pytest.raises(ConfigError, match="PHONE_NAME=.* is not a name"):
        load({**settings(tmp_path), "PHONE_NAME": name})


@pytest.mark.parametrize("kernel", ["missing.dylib", "."])
def test_a_kernel_that_is_not_an_existing_file_is_refused(tmp_path: Path, kernel: str) -> None:
    with pytest.raises(ConfigError, match="PHONE_KERNEL=.* is not a file that exists"):
        load({**settings(tmp_path), "PHONE_KERNEL": str(tmp_path / kernel)})
