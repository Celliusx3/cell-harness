# 02 A capability with missing keys stays off, and starts when they appear

**Status.** done

**What to build.** A server in the config may list the keys it `needs`. The
MCP service does not start a server while a needed key is missing, and its
status says which key. A new call starts or restarts one server, so a key
saved later turns it on with no restart of the harness. A needed key is
found in the server's `env` from the config files, then among the
capability keys in the keyring. `backend/config.json` lists the needs of
places, markets and instagram.

**Checks.** Unit tests: a server missing a needed key is not started and is
not offered to the model; once the key is in the keyring, starting it
connects it; `make dev` with keys in `config.local.json` connects all three
as before. `make lint` and `make test` are green.

**Blocked by.** none
