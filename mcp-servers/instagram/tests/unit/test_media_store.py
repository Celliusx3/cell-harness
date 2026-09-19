"""The media-root boundary, and the duration sidecar."""

from __future__ import annotations

from pathlib import Path

import pytest

from instagram.media import store as cache


@pytest.mark.parametrize(
    "shortcode",
    ["..", "../../etc/passwd", "a/b", "/absolute", "", "with space", "dot.dot", "a" * 65],
)
def test_a_shortcode_that_could_escape_the_root_is_refused(shortcode: str) -> None:
    with pytest.raises(cache.UnsafeShortcode):
        cache.directory_for(Path("/tmp/root"), shortcode)


def test_the_root_is_private_to_this_user(tmp_path: Path) -> None:
    root = tmp_path / "work"

    cache.directory_for(root, "C6NiA4lRux8")

    assert root.stat().st_mode & 0o777 == 0o700


def test_has_media_is_false_before_a_fetch_and_true_after(tmp_path: Path) -> None:
    root = tmp_path / "work"
    assert cache.has_media(root, "AAAAAAAAAA") is False

    (cache.directory_for(root, "AAAAAAAAAA") / "video.mp4").parent.mkdir(
        parents=True, exist_ok=True
    )
    (cache.directory_for(root, "AAAAAAAAAA") / "video.mp4").write_bytes(b"x")

    assert cache.has_media(root, "AAAAAAAAAA") is True


def test_duration_survives_the_gap_between_fetch_and_read(tmp_path: Path) -> None:
    root = tmp_path / "work"

    cache.remember_duration(root, "AAAAAAAAAA", 69.96)

    assert cache.recall_duration(root, "AAAAAAAAAA") == pytest.approx(69.96)


def test_an_absent_duration_is_none_rather_than_a_guess(tmp_path: Path) -> None:
    assert cache.recall_duration(tmp_path / "work", "AAAAAAAAAA") is None


def test_a_corrupt_duration_sidecar_does_not_fail_the_read(tmp_path: Path) -> None:
    root = tmp_path / "work"
    (cache.directory_for(root, "AAAAAAAAAA")).mkdir(parents=True, exist_ok=True)
    (cache.directory_for(root, "AAAAAAAAAA") / "duration.txt").write_text("not a number")

    assert cache.recall_duration(root, "AAAAAAAAAA") is None


def test_remembering_nothing_writes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "work"

    cache.remember_duration(root, "AAAAAAAAAA", None)

    assert cache.recall_duration(root, "AAAAAAAAAA") is None


def test_forget_removes_one_reel_and_reports_whether_there_was_anything(tmp_path: Path) -> None:
    root = tmp_path / "work"
    directory = cache.directory_for(root, "AAAAAAAAAA")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "video.mp4").write_bytes(b"x")

    assert cache.forget(root, "AAAAAAAAAA") is True
    assert cache.forget(root, "AAAAAAAAAA") is False


def test_the_sweep_drops_only_directories_older_than_the_cutoff(tmp_path: Path) -> None:
    root = tmp_path / "work"
    for code in ("OLDOLDOLD1", "NEWNEWNEW1"):
        directory = cache.directory_for(root, code)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "video.mp4").write_bytes(b"x")
    import os

    old = cache.directory_for(root, "OLDOLDOLD1")
    os.utime(old, (0, 0))

    removed = cache.sweep(root, older_than_seconds=3600)

    assert removed == 1
    assert not old.exists()
    assert cache.directory_for(root, "NEWNEWNEW1").exists()


def test_sweeping_a_root_that_does_not_exist_yet_is_zero_not_an_error(tmp_path: Path) -> None:
    assert cache.sweep(tmp_path / "never", older_than_seconds=1) == 0
