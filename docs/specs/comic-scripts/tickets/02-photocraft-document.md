# 02 The open PhotoCraft page, the text layers and the lock, each in its file

**Status.** done

**What to build.** `scripts/comic/document.py` takes from `lettering/photocraft.py` the open document (`Document` with `batch` and `save`, `opened`), its reply shapes (`Opened`, `Step`, `Batch`) and the wait for a saved file (`is_whole_image`, `settled`). A `BatchStep` model (`command: str`, `params: dict[str, JsonValue]`) replaces the loose step maps that `lettering/clean.py` and the text layers build. `lettering/photocraft.py` becomes `lettering/text_layers.py`: create, measure, resize and fit the layers as functions taking the document (`create_layers`, `measured_layers`, `resize_layers`, `fitted_layers`), `is_fitting`, the centring and `letter_document`. `held` moves from `connection.py` to `scripts/comic/lock.py`. Every caller and test imports the new place; the old names go.

**Checks.** `make test-skills` 125 passed at the same coverage, with a new test that a line too wide at its planned size shrinks until it fits, `make lint-skills` clean, no file over 300 lines. Breaks: the shrink step in `fitted_layers` not shrinking, and `held` not locking, each turn a test red.

**Blocked by.** 01
