# 02 · Every caller asks the image service, and the old store is gone

**Status.** done

**What to build.**
- The turn loop's `vision: ImageStore | None` becomes `images: ImageService | None`; `None` still means the model cannot see.
- `tool_run.py`, `web/runtime.py`, `web/server.py`, `channels/web/channel.py` and `channels/web/routes.py` call the service.
- The test helpers (`helpers.py`, `webapp.py`, `web_helpers.py`) and the 21 test files that pass `vision=` pass `images=`.
- Delete `session/images.py`, `runtime/images.py` and `test_image_store.py`. `test_runtime_images.py`, which tests the turn loop, passes `images=` like the rest.

It is mechanical, and over five files because the rename has to land in one go.

**Checks.** The whole backend suite passes at today's count plus ticket 01's tests. `grep -rn "ImageStore\|image_store(\|StoredImage\|session\.images\|runtime\.images\|attached_images\|result_images" backend` finds nothing, and no `Runtime(...)` passes `vision=`. The setting `llm.vision`, the yes or no that says whether the model can see, keeps its name.

**Blocked by.** 01
