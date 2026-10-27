# 02 Credentials list

**Status:** open

**What to build.**

- `GET /api/credentials` lists every keyring entry: its id, name, kind, the bots it serves, and its last four characters.
- For `custom`, the bots come from each bot's allowed keys. For `llm`, they come from each bot's model credential, which 03 adds.
- It replaces PR #43's list of fields from the settings file.
- The Credentials page shows the entries grouped by kind.
- The Keys page and its sidebar link go away; their keys now show here as Custom.

**Checks.**

- A route test: one entry of each kind is listed with its kind, its bots and its last four characters.
- No value appears in full in the response.
- By hand: a key saved through a bot's card shows on Credentials as Custom, with the bots allowed to use it.

**Blocked by.** 04
