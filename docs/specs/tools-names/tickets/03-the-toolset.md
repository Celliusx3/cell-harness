# 03 · The pipeline is the toolset

**Status.** open

**What to build.** `tools/pipeline.py` becomes `tools/toolset.py`, and `ToolPipeline` becomes `Toolset`. Every variable that holds one (`pipeline`) becomes `toolset`, the test helper `pipeline_for` becomes `toolset_for`, and the two test names that say pipeline say what they test.

**Checks.** `make lint` and `make test` green (1489 passed). `git grep -nwE "ToolPipeline|pipeline_for|harness\.tools\.pipeline" -- backend` finds nothing.

**Blocked by.** 02
