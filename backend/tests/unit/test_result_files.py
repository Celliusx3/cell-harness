"""Which files a worker's ready report names: in the chat's folder, or out of reach."""

from __future__ import annotations

from harness.tickets.domain.result_files import reported_files

FOLDER = "/data/files/chat-1"
PAGES = [f"{FOLDER}/page-1.jpg", f"{FOLDER}/page-2.jpg", f"{FOLDER}/page-10.jpg"]


def test_a_file_named_by_its_full_path_is_in_the_chat() -> None:
    found = reported_files(f"Saved {FOLDER}/page-1.jpg.", FOLDER, PAGES)

    assert found.in_chat == (f"{FOLDER}/page-1.jpg",)
    assert found.out_of_reach == ()


def test_files_listed_by_name_under_the_chat_s_folder_are_in_the_chat() -> None:
    summary = f"All pages saved to {FOLDER}/:\n\n- page-1.jpg (834 bytes)\n- page-2.jpg"

    found = reported_files(summary, FOLDER, PAGES)

    assert found.in_chat == (f"{FOLDER}/page-1.jpg", f"{FOLDER}/page-2.jpg")
    assert found.out_of_reach == ()


def test_a_bare_name_counts_only_when_the_report_names_the_chat_s_folder() -> None:
    found = reported_files("Saved page-1.jpg in your home folder.", FOLDER, PAGES)

    assert found.in_chat == ()


def test_a_bare_name_is_not_found_inside_a_longer_name() -> None:
    found = reported_files(f"Saved to {FOLDER}: page-10.jpg", FOLDER, [f"{FOLDER}/0.jpg", *PAGES])

    assert found.in_chat == (f"{FOLDER}/page-10.jpg",)


def test_a_path_outside_the_chat_is_out_of_reach() -> None:
    found = reported_files("It is at /home/pc/chapter.cbz", FOLDER, PAGES)

    assert found.out_of_reach == ("/home/pc/chapter.cbz",)
