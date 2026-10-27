# 01 Credentials list

**Status:** done

**What to build.**

- `harness/config/sections.py` marks each secret field with `json_schema_extra={"x-secret": True}`: the API key, both bot tokens, and the encryption key.
- It marks the encryption key `"x-readonly": True`, so the page never lists it.
- A pure module `harness/config/credentials.py` walks the `Settings` model and returns a tuple of `Credential`, one per secret field that is not read-only.
- A `Credential` has its dotted path, its section, its one-line description, and its last four characters, or none when unset. Its full value never leaves the harness.
- It also says when a `HARNESS_` environment variable sets it, which makes it read-only.
- `harness/web/routes/credentials.py` serves `GET /api/credentials`, and `web/server.py` mounts it.

**Checks.**

- A test builds `Settings` from a temp config pair. The list is the API key and both bot tokens, in that order, without the encryption key.
- It asserts a set key shows only its last four characters, and an unset one shows none.
- It asserts a key given by a `HARNESS_` variable is marked as set by the environment.
- A guard test fails when a text field whose name ends in `key` or `token` is not marked secret.
- By hand: `curl -s 127.0.0.1:4896/api/credentials` lists the three, and the API key never appears in full.

**Blocked by.** none
