# 05 Each name says what it gives back

**Status.** done

**What to build.** Rename, updating every caller and test, no old name left:

- Files: `lettering/snap.py` to `lettering/letter_lines.py`, `tests/unit/test_snap.py` to `test_letter_lines.py`.
- `cli.py`: `answered` to `command_result`, `described` to `validation_problems`.
- `steps/__init__.py`: `inside` to `absolute_path`.
- `steps/pages.py`: `natural` to `natural_key`, `unpack` to `copy_pages`, `measured` to `page_at`, `unpacked` to `unpack_comic`, `listing` to `list_pages`.
- `steps/view.py`: `saved_view` to `save_view`.
- `steps/write.py`: `recorded` to `record_attempt`, `lettered` to `letter_page`, `unchanged` to `keep_page_as_is`, `write` to `write_page`.
- `steps/cleanup.py`: `kept` to `file_to_keep`, `emptied` to `empty_all_but`, `cleanup` to `clean_up_work_folder`.
- `chapter/work.py`: `rgb` to `rgb_image`, `WorkFolder.page` to `WorkFolder.page_file`.
- `chapter/plan.py`: `plan_of` to `plans_of`.
- `lettering/bubble.py`: `_largest` to `_largest_rectangle`.
- `lettering/clean.py`: `_filling` to `_fill_contents`, `_selecting` to `_select_steps`, `misses` to `missed_erasures`, `clean` to `clean_page`, `erasure` to `erasure_of` and `erasures` to `erasures_of`, as `page_of` and `items_of` are named, so the `erasures` parameters and `erasure` loop variables no longer share their names.
- `steps/write.py`: its module docstring says it is the write step for one page, without listing its calls.
- `lettering/leftover.py`: `run` to `longest_run`, `holds_text` to `has_text`, `located` to `left_over_at`.
- `lettering/letter_lines.py`: `_bubble_colour` to `_bubble_mask`, `_inside` to `_flooded_inside`, `_letters` to `_letter_mask`, `_rows` to `_letter_rows`, `_lines` to `_line_boxes`, `_holds` to `_is_centre_inside`, `_reached` to `_lines_reached`, `_reach` to `_plain_reach`, `around` to `box_around`.
- `lettering/text_layers.py`: `_centring` to `_centring_steps`, `letter_document` to `letter_clean_page`, and the `texts` and `text` parameters of the layer functions and `is_fitting` to `layers` and `layer`.
- `document.py`: `settled` to `wait_until_readable`, `Document.batch` to `Document.run_steps`.
- Classes: `Answered` to `Answer`, `Refused` to `Refusal`, `SignedIn` to `SignInResult`, `Step` to `StepResult`, `Batch` to `BatchReply`, `Opened` to `OpenReply`, `Created` to `CreateReply`, `Placed` to `Placement`, `Lettered` to `TextLayer`.
- Bare tuples become named types: `Corners` for the spill check's area and for the strips and area in `letter_lines.py` and `bubble.py`, `Size` for the spill check's page size, a `Point(x, y)` for the seeds, `range` for runs of letter rows.

**Checks.** `make test-skills` 129 passed, `make lint-skills` clean, `make lint` clean; a grep for each old name in `.agents/skills/translate-comic` finds nothing.

**Blocked by.** 04
