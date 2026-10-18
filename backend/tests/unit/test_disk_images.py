"""Image bytes on disk: kept once under their hash, whole or not at all, and found by it."""

from __future__ import annotations

import base64
import hashlib
import os

import pytest

from harness.images import BLOBS, KEPT_MEDIA_TYPES, DiskImageRepository, ImageFile
from tests.mcp_stub import DOT_PNG

DOT = base64.b64decode(DOT_PNG)
DOT_SHA256 = hashlib.sha256(DOT).hexdigest()


def test_the_same_bytes_kept_twice_are_one_file(tmp_path) -> None:
    disk = DiskImageRepository(tmp_path / "blobs")

    disk.write(DOT_SHA256, "image/png", DOT)
    disk.write(DOT_SHA256, "image/png", DOT)

    assert [path.name for path in (tmp_path / "blobs").iterdir()] == [f"{DOT_SHA256}.png"]


def test_a_kept_file_is_never_rewritten(tmp_path) -> None:
    disk = DiskImageRepository(tmp_path)
    disk.write(DOT_SHA256, "image/png", DOT)
    (tmp_path / f"{DOT_SHA256}.png").write_bytes(b"left alone")

    disk.write(DOT_SHA256, "image/png", DOT)

    assert (tmp_path / f"{DOT_SHA256}.png").read_bytes() == b"left alone"


def test_the_images_live_in_the_blobs_folder_beside_the_sessions(tmp_path) -> None:
    DiskImageRepository(tmp_path / "sessions" / BLOBS).write(DOT_SHA256, "image/png", DOT)

    assert (tmp_path / "sessions" / "blobs" / f"{DOT_SHA256}.png").read_bytes() == DOT


def test_the_folder_is_readable_by_us_alone(tmp_path) -> None:
    DiskImageRepository(tmp_path / "blobs").write(DOT_SHA256, "image/png", DOT)

    assert (tmp_path / "blobs").stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize(
    ("media_type", "extension"),
    [("image/png", "png"), ("image/jpeg", "jpg"), ("image/webp", "webp"), ("image/gif", "gif")],
)
def test_each_type_is_kept_under_its_extension_and_found_by_hash(
    tmp_path, media_type: str, extension: str
) -> None:
    disk = DiskImageRepository(tmp_path)

    disk.write(DOT_SHA256, media_type, DOT)

    assert disk.file_of(DOT_SHA256) == ImageFile(
        path=tmp_path / f"{DOT_SHA256}.{extension}", media_type=media_type
    )


def test_a_write_that_fails_leaves_no_part_of_the_image(tmp_path, monkeypatch) -> None:
    def refuse(source: str, target: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", refuse)

    with pytest.raises(OSError, match="disk full"):
        DiskImageRepository(tmp_path).write(DOT_SHA256, "image/png", DOT)

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("media_type", sorted(KEPT_MEDIA_TYPES))
def test_every_type_an_image_may_be_kept_as_is_kept_and_found(tmp_path, media_type: str) -> None:
    disk = DiskImageRepository(tmp_path / "blobs")

    disk.write(DOT_SHA256, media_type, DOT)

    found = disk.file_of(DOT_SHA256)

    assert disk.read(DOT_SHA256, media_type) == DOT
    assert found is not None and found.media_type == media_type
