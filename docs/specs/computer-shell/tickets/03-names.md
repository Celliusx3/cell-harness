# 03 · Names that say what they return

**Status.** done

**What to build.**
- `config.py`: `required` → `required_value`, `folder` → `existing_folder`.
- `shell.py`: `_python` → `_run_python`, `_exec` → `_exec_arguments`, `SEEN` → `SEEN_JOB`.
- `jobs.py`: the in-computer `runs(folder)` → `is_running(folder)`, and `RUNS_DEFINITION` → `IS_RUNNING_DEFINITION`.
- `machine.py`: `_inspected` → `_inspect_output`.

**Checks.** The computer suite stays green at the same count. Grepping for each old name finds nothing.

**Blocked by.** 01
