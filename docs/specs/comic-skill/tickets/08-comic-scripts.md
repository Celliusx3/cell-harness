# 08 The comic steps as skill scripts

**Status.** done

**What to build.** Move the stashed comic package (`chapter/`, `lettering/`, `steps/`, models) into `.agents/skills/translate-comic/scripts/comic/`, with its tests. The PhotoCraft calls use ticket 07's client. A CLI `run.py` has `pages <file>`, `write <work> <page>` (items as JSON on stdin) and `cleanup <work> <keep>`, each printing one JSON result. The attempt count is kept in `translations.json`. Each page's parts are saved as JPEGs of 5 MiB or less for `view_image`.

**Checks.** The moved unit tests pass (79 before the move), and a CLI test runs `pages` then `write` against the fake PhotoCraft server and reads the result.

**Blocked by.** 07
