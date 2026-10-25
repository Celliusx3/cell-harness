# 01 App settings

**Status:** open

**What to build.**

- `harness/config/settings.py` reads the local settings path from `HARNESS_CONFIG_LOCAL`. Today's sibling path stays the default.
- A new `desktop/config.json` holds the app's committed settings. It copies the `llm` values from `backend/config.json`.
- Every data path in it sits under `~/Library/Application Support/Cell Harness/`, with its own editable skills folder there.
- It lists only the native approval tools, and `mcp.servers` is empty.
- A new `backend/tests/unit/test_desktop_settings.py` holds the check.

**Checks.**

- A test runs a Python child with `HOME` set to a temp folder and `HARNESS_CONFIG` set to `desktop/config.json`.
- The child also gets `HARNESS_CONFIG_LOCAL`, set to a temp file holding `llm.api_key`. It prints the loaded settings.
- The test asserts the key came from the temp file and `mcp.servers` is empty.
- It asserts every data path is under `<HOME>/Library/Application Support/Cell Harness/`.
- By hand: run the harness on port 4886 with these two variables, and chat once in a browser.

**Blocked by.** none
