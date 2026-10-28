# 01 Typed keyring

**Status:** done

**What to build.**

- The sealed keyring's entries gain a kind: `custom`, `llm`, `telegram` or `discord`. The kinds form a discriminated union, typed per kind.
- A `custom` entry is today's saved key: a name, its destination, and the sealed value.
- An `llm` entry adds the endpoint and the model, which are not secret. A `telegram` or `discord` entry holds only its token.
- An entry in today's keyring file, which has no kind, is read as `custom`, so every saved key survives.
- Files: `harness/secrets/models/`, `harness/secrets/service.py`, and the repository's reader.
- Nothing a person sees changes.

**Checks.**

- A keyring file written before this change loads, and each entry is `custom` with the same name, destination and value.
- Saving and reading one entry of each kind round-trips, with the value sealed on disk.
- The existing keyring, Keys page and `fetch_with_secret` tests pass unchanged.

**Blocked by.** none
