# 01 · One chat file service, built at startup

**Status.** done

**What to build.** `build_runtime` (`web/runtime.py`) takes a keyword-only `files: ChatFileService` instead of building its own, and gives it to the three file tools and to `Runtime(files=...)`. `create_web_app` (`web/server.py`) passes the one it already builds. Every test caller of `build_runtime` passes `files_in(tmp_path)`.

**Checks.** The startup test in `tests/integration/test_web_image_service.py`, or one beside it, also shows that the web channel and the runtime hold the same chat file service. Breaking the hand-over turns it red. The whole suite stays green.

**Blocked by.** none
