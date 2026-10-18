"""The image rules: which types a model is sent, the 5 MB cap, and bytes that still match a hash."""

from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path

import pytest

from harness.files import ChatFile
from harness.images import IMAGE_MAX_BYTES, DiskImageRepository, ImageFile, ImageService
from harness.llm import Image, Text
from harness.prompts import IMAGE_TOO_LARGE
from harness.tools.definition import ReturnedImage
from tests.mcp_stub import DOT_PNG

DOT = base64.b64decode(DOT_PNG)
DOT_SHA256 = hashlib.sha256(DOT).hexdigest()
DOT_IMAGE = Image(media_type="image/png", sha256=DOT_SHA256, size=len(DOT))
RETURNED_DOT = ReturnedImage(media_type="image/png", data=DOT)


class FullDisk:
    """A repository that keeps nothing: every write fails as a full disk would."""

    def write(self, sha256: str, media_type: str, data: bytes) -> None:
        raise OSError("disk full")

    def read(self, sha256: str, media_type: str) -> bytes:
        raise OSError("nothing was kept")

    def file_of(self, sha256: str) -> ImageFile | None:
        return None


def images_at(folder: Path) -> ImageService:
    return ImageService(DiskImageRepository(folder))


def attached(path: Path, *, media_type: str = "image/png", size: int | None = None) -> ChatFile:
    return ChatFile(
        path=str(path),
        name=path.name,
        media_type=media_type,
        size=path.stat().st_size if size is None else size,
    )


def test_a_kept_image_carries_its_size_in_bytes(tmp_path) -> None:
    (kept,) = images_at(tmp_path).of_result((RETURNED_DOT,))

    assert isinstance(kept, Image)
    assert kept.size == len(DOT)


def test_the_same_bytes_returned_twice_are_one_kept_image(tmp_path) -> None:
    blocks = images_at(tmp_path).of_result((RETURNED_DOT, RETURNED_DOT))

    assert blocks == (DOT_IMAGE, DOT_IMAGE)
    assert [path.name for path in tmp_path.iterdir()] == [f"{DOT_SHA256}.png"]


def test_a_reload_reads_the_same_bytes_by_hash(tmp_path) -> None:
    assert images_at(tmp_path).of_result((RETURNED_DOT,)) == (DOT_IMAGE,)

    assert images_at(tmp_path).read(DOT_IMAGE) == DOT


def test_a_missing_image_reads_as_nothing_with_a_warning(tmp_path, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="harness.images"):
        read = images_at(tmp_path).read(
            Image(media_type="image/png", sha256=DOT_SHA256, size=len(DOT))
        )

    assert read is None
    assert f"image {DOT_SHA256} could not be read" in caplog.text


def test_a_file_that_no_longer_holds_its_bytes_reads_as_nothing(tmp_path, caplog) -> None:
    images = images_at(tmp_path)
    images.of_result((RETURNED_DOT,))
    (tmp_path / f"{DOT_SHA256}.png").write_bytes(b"swapped")

    with caplog.at_level(logging.WARNING, logger="harness.images"):
        assert images.read(DOT_IMAGE) is None
    assert "no longer holds the bytes" in caplog.text


@pytest.mark.parametrize(
    "image",
    [
        Image(media_type="image/png", sha256="../../etc/passwd", size=3),
        Image(media_type="image/png", sha256=DOT_SHA256.upper(), size=len(DOT)),
        Image(media_type="image/bmp", sha256=DOT_SHA256, size=len(DOT)),
    ],
)
def test_an_image_that_cannot_name_a_kept_file_reads_as_nothing(tmp_path, image: Image) -> None:
    assert images_at(tmp_path).read(image) is None


def test_a_kept_image_is_found_by_its_hash(tmp_path) -> None:
    images = images_at(tmp_path)
    images.of_result((RETURNED_DOT,))

    assert images.file_of(DOT_SHA256) == ImageFile(
        path=tmp_path / f"{DOT_SHA256}.png", media_type="image/png"
    )


@pytest.mark.parametrize("sha256", ["", "abc", "../" + DOT_SHA256, "g" * 64, DOT_SHA256.upper()])
def test_a_name_that_is_not_a_hash_finds_no_file(tmp_path, sha256: str) -> None:
    images = images_at(tmp_path / "blobs")
    images.of_result((RETURNED_DOT,))
    (tmp_path / f"{DOT_SHA256}.png").write_bytes(DOT)

    assert images.file_of(sha256) is None


def test_a_hash_with_no_file_finds_nothing(tmp_path) -> None:
    assert images_at(tmp_path).file_of(DOT_SHA256) is None


def test_a_returned_image_over_five_megabytes_is_a_note_instead(tmp_path) -> None:
    huge = ReturnedImage(media_type="image/png", data=bytes(IMAGE_MAX_BYTES + 1))

    blocks = images_at(tmp_path / "blobs").of_result((huge,))

    note = IMAGE_TOO_LARGE.format(size=IMAGE_MAX_BYTES + 1, limit=IMAGE_MAX_BYTES)
    assert blocks == (Text(text=note),)
    assert not (tmp_path / "blobs").exists()


def test_a_returned_type_no_model_is_sent_is_not_shown(tmp_path, caplog) -> None:
    bitmap = ReturnedImage(media_type="image/bmp", data=DOT)

    with caplog.at_level(logging.WARNING, logger="harness.images"):
        blocks = images_at(tmp_path / "blobs").of_result((bitmap,))

    assert blocks == ()
    assert "a tool's image/bmp image is not shown: no model is sent that type" in caplog.text
    assert not (tmp_path / "blobs").exists()


def test_a_returned_image_that_cannot_be_kept_is_not_shown(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="harness.images"):
        blocks = ImageService(FullDisk()).of_result((RETURNED_DOT,))

    assert blocks == ()
    assert "an image is not shown: it could not be kept: disk full" in caplog.text


def test_an_attached_image_is_kept_and_shown(tmp_path) -> None:
    (tmp_path / "page.png").write_bytes(DOT)
    images = images_at(tmp_path / "blobs")

    assert images.of_attachments((attached(tmp_path / "page.png"),)) == (DOT_IMAGE,)
    assert images.read(DOT_IMAGE) == DOT


def test_an_attached_image_over_five_megabytes_is_not_shown(tmp_path) -> None:
    (tmp_path / "huge.png").write_bytes(DOT)
    huge = attached(tmp_path / "huge.png", size=IMAGE_MAX_BYTES + 1)

    assert images_at(tmp_path / "blobs").of_attachments((huge,)) == ()
    assert not (tmp_path / "blobs").exists()


@pytest.mark.parametrize("media_type", ["text/plain", "image/bmp"])
def test_an_attached_file_that_is_not_an_image_is_left_to_its_line(
    tmp_path, media_type: str
) -> None:
    (tmp_path / "notes").write_bytes(DOT)
    notes = attached(tmp_path / "notes", media_type=media_type)

    assert images_at(tmp_path / "blobs").of_attachments((notes,)) == ()
    assert not (tmp_path / "blobs").exists()


def test_an_attached_image_that_cannot_be_read_is_left_to_its_line(tmp_path, caplog) -> None:
    gone = ChatFile(
        path=str(tmp_path / "gone.png"), name="gone.png", media_type="image/png", size=8
    )

    with caplog.at_level(logging.WARNING, logger="harness.images"):
        images = images_at(tmp_path / "blobs").of_attachments((gone,))

    assert images == ()
    assert "gone.png is not shown" in caplog.text


def test_an_image_that_cannot_be_kept_is_not_shown(tmp_path, caplog) -> None:
    (tmp_path / "page.png").write_bytes(DOT)

    with caplog.at_level(logging.WARNING, logger="harness.images"):
        images = ImageService(FullDisk()).of_attachments((attached(tmp_path / "page.png"),))

    assert images == ()
    assert "could not be kept" in caplog.text
