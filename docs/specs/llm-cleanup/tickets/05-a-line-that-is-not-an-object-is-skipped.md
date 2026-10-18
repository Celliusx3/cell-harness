# 05 · A streamed line that is not an object is skipped, not fatal

**Status.** open

**What to build.** A fix. In `llm/adapters/openai.py`, a line whose JSON is not an object (`5`, `null`), or whose first choice is not an object, is skipped with a warning, the same as a line that is not JSON. Regression test in `tests/unit/test_openai_stream_edges.py`.

**Checks.** The regression test fails on the code as it is (the reply raises `AttributeError`), then passes. Break: undo the skip; the test fails.

**Blocked by.** 01
