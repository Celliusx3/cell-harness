# 03 The write step only runs the step

**Status.** done

**What to build.** `scripts/comic/lettering/spills.py` takes the spill check from `steps/write.py` as a pure function over the clean and English images and the plans (`spilling_lines`, `spilled_pixels`, `_checked_area`), its numbers named in full (`INK_DIFFERENCE`, `OTHER_COLOUR_DIFFERENCE`, `EDGE_NEAR_PX`, `CHECKED_AREA_SHARE`, `MOST_SPILLED_PIXELS`). `erasure` and an `erasures(original, planned)` over the page's image move to `lettering/clean.py` beside `Erasure`, with `LINE_PAD`. `placements(cleaned, erased)` over the clean image moves to `lettering/bubble.py` beside `letter_box`. `steps/write.py` reads the images and calls them.

**Checks.** `make test-skills` 128 passed, with new tests that a line drawn across a bubble's outline spills and one inside does not, and that two lines in one bubble keep their letter boxes off each other, `make lint-skills` clean. Break: the spill threshold raised past any spill turns a test red.

**Blocked by.** 02
