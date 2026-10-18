# 07 · The native helpers are private, and the bots files are named for their tools

**Status.** open

**What to build.**
- `native/files/`: `archive.py`, `chat_paths.py`, `image.py` and `descriptions.py` become `_archive.py`, `_chat_paths.py`, `_image.py` and `_descriptions.py`.
- `native/code/typescript.py` becomes `_typescript.py`. `prompts.py` keeps its name, because the code door exports from it.
- `native/bots/tools.py` becomes `create.py`.
- The imports inside each folder follow, and so do the tests that import those files, and the line in `mcp-servers/README.md` that names the TypeScript printer.

**Checks.** `make lint` and `make test` green (1486 passed). `git grep -nE "native/files/(archive|chat_paths|image|descriptions)\.py|native/code/typescript\.py|native/bots/tools\.py|native\.files\.(archive|chat_paths|image|descriptions)\b|native\.code\.typescript\b|native\.bots\.tools\b" -- . ':!docs/specs'` finds nothing. Break: import `harness.tools.native.files._archive` from `harness/web/runtime.py`; `test_no_package_imports_another_package_s_private_module` fails.

**Blocked by.** 06
