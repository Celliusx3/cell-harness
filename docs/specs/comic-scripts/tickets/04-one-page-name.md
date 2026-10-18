# 04 A page has one name

**Status.** done

**What to build.** `WorkFolder` in `chapter/work.py` takes the page's file name (`001.png`) in `clean_png`, `english_png`, `page_view` and `english_view`, and works out the stem in one private method. Every `Path(name).stem` and every `stem` argument in `steps/write.py`, `steps/view.py`, `lettering/clean.py` and `lettering/text_layers.py` goes; tests pass the file name.

**Checks.** `make test-skills` 129 passed, with a new test pinning the clean, English and view file names of a page, `make lint-skills` clean; `grep -rn "\.stem" comic` finds only the work folder's one method. Break: that method returning the file name unchanged turns a test red.

**Blocked by.** 03
