# 02 · The shared-folder rules in their own module

**Status.** done

**What to build.** Move `Mount`, `MOUNTS`, `shared_folders`, `volume_arguments` and `is_mounted_as_configured` from `computer/machine.py` into a new `computer/mounts.py`. Update their imports and tests. No behaviour change.

**Checks.** The computer suite stays green at the same count. `machine.py` is well under 300 lines.

**Blocked by.** 01
