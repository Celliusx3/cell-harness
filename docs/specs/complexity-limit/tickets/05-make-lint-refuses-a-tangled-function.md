# 05 · `make lint` refuses a function past a complexity of 10

**Status.** done

**What to build.**
- `backend/pyproject.toml`: ruff selects `C90` and sets `[tool.ruff.lint.mccabe] max-complexity = 10`.
- `CLAUDE.md` rules: one line beside the file cap, "**Every function under complexity 10.** `make lint` refuses a more tangled one; split on the seam, never raise the cap."
- `docs/rules.md`: the reasoning beside the file-length rule, and the Makefile help line names the check.

**Checks.** `make lint` and `make test` green. Break: make one function past 10 on purpose; `make lint` fails naming it; undo.

**Blocked by.** 01, 02, 03
