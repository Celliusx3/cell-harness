# 04 · The docs name the new files and classes

**Status.** open

**What to build.** `CLAUDE.md`'s layout line and its rule that the pipeline refuses an unshown call, `README.md`'s layout line, and each doc that names `ToolDefinition`, `ToolPipeline`, `ApprovalGate`, `ClientTools.definitions()` or the files by path follow. `DESIGN.md` and the source teardowns stay.

**Checks.** `make lint` and `make test` green (1489 passed). `git grep -nE "ToolDefinition|ToolPipeline|ApprovalGate|definitions\(\)|tools/(definition|pipeline|approval)\.py" -- '*.md' ':!docs/specs' ':!DESIGN.md' ':!docs/deepseek-harness.md' ':!docs/cell-bot.md' ':!docs/without-cordis.md'` finds nothing.

**Blocked by.** 03
