# 03 · One image service, built at startup

**Status.** done

**What to build.** `create_web_app` in `web/server.py` builds one `ImageService` over one `DiskImageRepository` under the sessions folder's `blobs`, and hands it to `build_runtime` (in `web/runtime.py`) and to `build_channels`. The eight test files that call either builder pass it: `test_compose_skills.py`, `test_compose_code.py`, `test_compose_subagent.py`, `test_every_feature_has_a_tool.py`, `test_create_skill.py`, `test_discord.py`, `test_telegram.py` and `test_web_files.py`.

**Checks.** A new test: the web channel and the runtime hold the image service startup built. Breaking the hand-over turns it red. The whole suite stays green.

**Blocked by.** 02
