"""Startup refusals, and the shared name the phone runs under by default."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from phone.config import IMAGE as PUBLISHED_IMAGE
from phone.config import ConfigError, load

IMAGE = "ghcr.io/celliusx3/cell-harness/phone@sha256:" + "1" * 64
KERNEL_BYTES = b"\x00"


def settings(tmp_path: Path) -> dict[str, str]:
    kernel = tmp_path / "libkrunfw.5.dylib"
    kernel.write_bytes(KERNEL_BYTES)
    files = tmp_path / "files"
    files.mkdir(exist_ok=True)
    return {
        "PHONE_IMAGE": IMAGE,
        "PHONE_KERNEL": str(kernel),
        "PHONE_KERNEL_SHA256": hashlib.sha256(KERNEL_BYTES).hexdigest(),
        "PHONE_FILES_DIR": str(files),
    }


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


@pytest.mark.parametrize("variable", ["PHONE_KERNEL", "PHONE_KERNEL_SHA256", "PHONE_FILES_DIR"])
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


def test_the_chat_files_folder_loads_resolved(tmp_path: Path) -> None:
    env = {**settings(tmp_path), "PHONE_FILES_DIR": str(tmp_path / "files" / ".." / "files")}

    assert load(env).files_dir == (tmp_path / "files").resolve()


@pytest.mark.parametrize("files", ["missing", "libkrunfw.5.dylib"])
def test_chat_files_that_are_not_an_existing_folder_are_refused(tmp_path: Path, files: str) -> None:
    env = {**settings(tmp_path), "PHONE_FILES_DIR": str(tmp_path / files)}

    with pytest.raises(ConfigError, match="PHONE_FILES_DIR=.* is not a folder that exists"):
        load(env)


def test_the_idle_minutes_default_to_ten_and_can_be_set(tmp_path: Path) -> None:
    assert load(settings(tmp_path)).idle_minutes == 10
    assert load({**settings(tmp_path), "PHONE_IDLE_MINUTES": " 1 "}).idle_minutes == 1


@pytest.mark.parametrize(
    ("raw", "refusal"),
    [
        ("ten", "PHONE_IDLE_MINUTES='ten' is not a whole number"),
        ("1.5", "PHONE_IDLE_MINUTES='1.5' is not a whole number"),
        ("0", "PHONE_IDLE_MINUTES=0 must be greater than zero"),
        ("-3", "PHONE_IDLE_MINUTES=-3 must be greater than zero"),
    ],
)
def test_idle_minutes_that_are_not_a_positive_whole_number_are_refused(
    tmp_path: Path, raw: str, refusal: str
) -> None:
    with pytest.raises(ConfigError, match=re.escape(refusal)):
        load({**settings(tmp_path), "PHONE_IDLE_MINUTES": raw})


def test_a_kernel_that_is_not_the_pinned_one_is_refused(tmp_path: Path) -> None:
    env = settings(tmp_path)
    Path(env["PHONE_KERNEL"]).write_bytes(b"\x01")

    with pytest.raises(
        ConfigError, match="PHONE_KERNEL is not the kernel PHONE_KERNEL_SHA256 pins"
    ):
        load(env)


def test_the_pin_is_read_without_case_or_spaces_mattering(tmp_path: Path) -> None:
    env = settings(tmp_path)

    assert load({**env, "PHONE_KERNEL_SHA256": f" {env['PHONE_KERNEL_SHA256'].upper()} "})


def test_without_an_image_set_the_phone_runs_the_published_one_by_digest(tmp_path: Path) -> None:
    env = {**settings(tmp_path), "PHONE_IMAGE": " "}

    assert load(env).image == PUBLISHED_IMAGE
    assert PUBLISHED_IMAGE.startswith("ghcr.io/celliusx3/cell-harness/phone@sha256:")
