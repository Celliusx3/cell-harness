# 02 · The docs name the tool service

**Status.** done

**What to build.** Every doc that names the registry or the dispatcher as a part of this code names the tool service or its `dispatch` instead: the layout line and the two dispatch rules in `CLAUDE.md`, the layout line in `README.md`, and `docs/rules.md`, `docs/mcp-tool-scaling.md`, `docs/client-data.md`, `docs/mcp-apps.md` and `docs/skills.md`. `DESIGN.md` and the source teardowns (`docs/deepseek-harness.md`, `docs/cell-bot.md`, `docs/without-cordis.md`) describe the first proposal and other projects, and stay.

**Checks.** `make lint` and `make test` green (1489 passed). `git grep -nwiE "dispatcher|ToolRegistry|ToolDispatcher" -- '*.md' ':!docs/specs' ':!DESIGN.md' ':!docs/deepseek-harness.md' ':!docs/cell-bot.md' ':!docs/without-cordis.md'` finds nothing.

**Blocked by.** 01
