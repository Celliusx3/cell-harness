# 09 The skill text, the docs, and a run in the chat

**Status.** open

**What to build.** `.agents/skills/translate-comic/SKILL.md`: the workflow in the spec, naming `computer__shell`, `view_image`, `make_archive` and `send_file`, with the box, original and left-over rules the old tool descriptions carried. Update `CLAUDE.md` (a capability can be a skill's scripts run in the computer; where their tests live), `PHASES.md` (Phase 13 lands in the computer), `mcp-servers/README.md`, and repoint the comic rows of `docs/prompt-failures.md`.

**Checks.** In the chat, with GLM, the five Japanese pages come back as an English archive with a clear report, and the working folder holds only the archive.

**Blocked by.** 04, 05, 06, 08

**Check result, 2026-10-17.** Built and run in the chat on GLM-5.3 Flash X. The five Japanese pages came back as `bjy-1-english.cbz`, sent, with the work folder cleaned to the archive alone; but the report was not clear (every page kept `cut_off`, `spills` or `left_over` after 3 attempts, page 5 with 10 left-over areas), because GLM's boxes often missed their bubbles. The one-page seven-language archive on the final code came back clear except the screentone decoy. Open on the clear-report clause.
