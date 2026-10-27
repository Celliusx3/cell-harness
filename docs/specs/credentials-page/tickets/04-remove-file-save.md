# 04 Remove the settings-file save

**Status:** open

**What to build.**

- PR #43's save into the settings file goes away: the `PUT` that wrote `config.local.json`, the merge and writer module, and the field markers.
- The Mac app's watcher that restarts the harness when that file changes goes away, and so does `make dev`'s `--reload-include config.local.json`.
- Nothing writes the settings file from a page any more.

**Checks.**

- No caller of the removed names is left (`grep` across `backend`, `frontend` and `desktop`).
- `make test` and `make test-desktop` pass.

**Blocked by.** 03
