# 01 Render refuses a chapter with untranslated pages

**Status.** done

**What to build.** In `Celliusx3/skills`, `comic-translator/scripts/run.py render` first checks every page's notes. Any entry with an empty `translation` stops it with one `error:` line naming the pages, for example `error: pages 012, 013 still have untranslated entries; translate them first`. A page whose entries were all deleted counts as done. The check is a plain function in `comic_translator/notes.py`, with a test beside the package's other tests.

**Checks.** A test builds a work folder whose page 012 has one entry with an empty translation. `render` answers the error naming 012 and writes no `translated/` page. With every entry translated, `render` runs as before. `pytest` in the skill's `scripts/` passes with coverage of 80% or more.

**Blocked by.** none
