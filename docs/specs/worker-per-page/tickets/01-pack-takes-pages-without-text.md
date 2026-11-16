# 01 Combine packs a page with no text as it is

**Status.** done

**What to build.** In `Celliusx3/skills`, `comic-translator/scripts/run.py`. `detect` adds `text_pages` to the JSON it prints: the names of the pages whose notes hold at least one entry, in page order. `pack` takes a page whose notes hold no entry from `pages/` unchanged, so it needs no render. The rule that decides which pages need a render is a plain function in `comic_translator/notes.py`, beside `untranslated_pages`.

**Checks.** A test builds a work folder whose page 02 has no entries and was never rendered. `pack` writes an archive with every page, and its page 02 is byte for byte `pages/02.jpg`. A page with entries and no render is still refused, as today. `detect` on a two-page source where one page has text prints `text_pages` naming only that page. `uv run pytest` in the skill's `scripts/` passes with coverage of 80% or more, and `ruff check` and `ruff format --check` are clean.

**Blocked by.** none
