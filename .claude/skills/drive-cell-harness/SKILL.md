---
name: drive-cell-harness
description: Start a private copy of cell-harness (FastAPI backend + Next.js chat UI) on its own ports and data folder, drive the browser chat the way a person does with the Playwright MCP tools, and capture proof. Use to verify any change a person would see in the chat, a tool card, an approval card, or the Skills page.
---

# Drive cell-harness

The surface is the browser chat at `http://localhost:4997` (this copy). The backend answers `/api/*` behind it. Telegram and Discord are other clients of the same backend; this copy never connects to them.

## Launch

From the checkout being proved (a worktree is fine), with a scratch folder `$RUN` you own:

```sh
RUN=<scratchpad>/drive-run && mkdir -p "$RUN"
[ -f "$RUN/encryption_key" ] || (umask 077 && openssl rand -hex 32 > "$RUN/encryption_key")
cd backend && uv sync --quiet && cd ..
[ -f "$RUN/config.local.json" ] || (umask 077 && echo '{}' > "$RUN/config.local.json")
[ -d frontend/node_modules ] || (cd frontend && npm ci --silent)
cd backend && HARNESS_CONFIG_LOCAL="$RUN/config.local.json" \
  HARNESS_SESSIONS__ROOT="$RUN/harness/sessions" \
  HARNESS_FILES__ROOT="$RUN/harness/files" \
  HARNESS_APPROVAL__GRANTS_PATH="$RUN/harness/approvals.json" \
  HARNESS_BOTS__PATH="$RUN/harness/bots.json" \
  HARNESS_SCHEDULES__PATH="$RUN/harness/schedules.json" \
  HARNESS_SECRETS__PATH="$RUN/harness/secrets.json" \
  HARNESS_SECRETS__ENCRYPTION_KEY="$(cat "$RUN/encryption_key")" \
  HARNESS_WEB__PUBLIC_URL="" \
  uv run uvicorn harness.web.server:create_web_app --factory --host 127.0.0.1 --port 4996 \
  > "$RUN/backend.log" 2>&1 &
echo $! > "$RUN/backend.pid"; cd ..
cd frontend && BACKEND_PORT=4996 npx next dev -p 4997 > "$RUN/frontend.log" 2>&1 &
echo $! > "$RUN/frontend.pid"; cd ..
```

Once the backend answers, give the copy a model: the first LLM credential in the person's own keyring, saved on the copy through `POST /api/credentials` and picked for Assistant through `PUT /api/bots/assistant`, without printing the key. A copy that already holds an LLM credential is left alone.

```sh
MAIN="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
(cd backend && uv run python - "$MAIN/backend/config.local.json") <<'PY'
import json, os, sys
from pathlib import Path
import httpx
from harness.secrets import DiskSecretRepository, SecretService
from harness.secrets.models.details import ModelDetails
copy = httpx.Client(base_url="http://127.0.0.1:4996", headers={"origin": "http://localhost:4997"})
if any(c["details"]["kind"] == "llm" for c in copy.get("/api/credentials").json()["credentials"]):
    sys.exit(0)
local = Path(sys.argv[1])
held = json.loads(local.read_text()).get("secrets", {}) if local.exists() else {}
encryption_key = os.environ.get("HARNESS_SECRETS__ENCRYPTION_KEY") or held.get("encryption_key")
if not encryption_key:
    sys.exit(f"no encryption key: neither HARNESS_SECRETS__ENCRYPTION_KEY nor {local} holds one")
path = Path(held.get("path", "~/.harness/secrets.json")).expanduser()
keyring = SecretService(DiskSecretRepository(path), encryption_key=encryption_key)
name = next((c.name for c in keyring.saved_credentials() if isinstance(c.details, ModelDetails)), None)
if name is None:
    sys.exit(f"no LLM credential in {path}: save one on the person's Credentials page")
model = keyring.model_credential_named(name)
draft = {"name": name, "details": model.details.model_dump(), "value": model.key.get_secret_value(), "bot_ids": []}
copy.post("/api/credentials", json=draft).raise_for_status()
assistant = next(bot for bot in copy.get("/api/bots").json() if bot["id"] == "assistant")
edit = {"name": assistant["name"], "instructions": assistant["instructions"], "model": name}
copy.put("/api/bots/assistant", json=edit).raise_for_status()
print(f"Assistant answers on {model.details.model} at {model.details.base_url}")
PY
```

For a check that needs no real key, run two fake OpenAI-compatible servers on localhost and save them on the copy's Credentials page instead: an endpoint may be `http` on localhost.

Run both with the Bash tool's `run_in_background`, or keep the `&` and the pid files. Ready when `curl -s localhost:4996/api/bots` prints a JSON list and `curl -s -o /dev/null -w '%{http_code}' localhost:4997` prints `200`. The copy starts with no MCP server; add each one it needs, `computer` too, as in [features/mcp-servers.md](features/mcp-servers.md). The first start of a `uv run --project ../mcp-servers/...` server installs it, so allow a minute.

Why each variable: the sessions root, files root, grants file, bots file, schedules file and secrets file keep the person's `~/.harness` untouched, and helper logs land beside the sessions root (`$RUN/harness/helpers`). The encryption key is the copy's own, kept in `$RUN` so a restart can still open the keys it saved; the server refuses to start without one. `HARNESS_CONFIG_LOCAL` points at an empty scratch file, so the copy reads no settings of the person's: it must never be `backend/config.local.json`. Every key the copy holds is in its own keyring, saved there by the step above or on its Credentials page. Never save the person's Telegram or Discord token on the copy: a copy with one answers the person's real chats.

## Doctor

```sh
lsof -nP -iTCP:4996 -iTCP:4997 -sTCP:LISTEN
grep -E "channel registered|ERROR|connected" "$RUN/backend.log" | tail
```

Both ports must belong to the pids in `$RUN/*.pid`. The log must say `web channel registered (pull)` and must not say `telegram channel registered`. A port held by another process is the person's own copy: pick other ports, never kill it.

Check which model this copy talks to before blaming the code: Assistant's LLM credential on the copy's Credentials page names its endpoint (for example LM Studio on `localhost:1234`). For LM Studio, `~/.lmstudio/bin/lms ps` shows the loaded `CONTEXT` and `PARALLEL`; a request over the context fails as "Context length exceeded", and requests running at once share that context, so with `PARALLEL` above 1 they fail together as "failed to decode". Load with `lms load <model> --context-length 16384 --parallel 1` to have LM Studio queue them.

## Drive

Load the browser tools with ToolSearch (`select:mcp__plugin_everything-claude-code_playwright__browser_navigate,...browser_snapshot,...browser_type,...browser_click,...browser_take_screenshot,...browser_wait_for,...browser_close`). Then:

1. `browser_navigate` to `http://localhost:4997`.
2. `browser_snapshot`, find the textbox with placeholder "Send a message", `browser_type` the prompt into it, `browser_click` the button labelled "Send".
3. The URL becomes `/c/<conversation id>`. Under your message, the bot's name and "Thinking" show at once. The header under the bot's name reads "Working · 0:07" and counts up.
4. While tools run, a line names the step, "Running <tool> · N tools", or "Thinking · N tools" between steps, with the tool cards open under it. When the reply starts, the line folds to "Used N tools", with "· M failed" when tools failed.
5. The turn has ended when the header reads "Ready". Do not wait for "Stop" to disappear: it also hides while the message box holds text.
6. Click "Used N tools" to unfold a finished turn's cards, then click a tool card's name (for example "run subagent") to open it: its arguments and its result appear under it.
7. An approval card offers "Allow once", "Allow for this conversation", "Always allow" and "Deny".

Handles: placeholder "Send a message" ("Reply, and it is answered after this turn" during a turn), labels "Send", "Stop", "More" (a menu of "Compact" and "Clear chat"), "New" (a menu of "Bot" and "Group"), "Edit bot", "Archive", "Restore", "Delete". The sidebar's foot has "Bots", "Computer" and "Settings". The Settings menu has "Back to chats", "Credentials", "MCP servers", "Approvals" and "Skills". The Credentials page has "Add credential", "Edit" and "Remove", and a bot's page "Link Telegram" and "Link Discord". Never click by coordinates.

## Evidence

Under `$RUN/evidence/`: a `browser_take_screenshot` after the action and after the turn ends (the tool may only write inside the folder Claude Code was started in, so give it a bare file name and `mv` the file into `$RUN/evidence/` at once; its snapshots land in that folder's `.playwright-mcp/`, delete the ones this run made), the conversation as stored (`curl -s localhost:4996/api/conversations/<id> > $RUN/evidence/conversation.json`), and any side effect the feature promises, such as files under `$RUN/harness/subagents/`. Quote the model's answer from the stored conversation, not from memory.

## Cleanup

```sh
kill "$(cat "$RUN/backend.pid")" "$(cat "$RUN/frontend.pid")"
```

`uv run` and `npx` start children that hold the ports: also kill the pids `lsof -nP -iTCP:4996 -iTCP:4997 -sTCP:LISTEN` shows. Then `browser_close`. Kill only these pids, never by name. If the browser tool says "Browser is already in use", the headless Chrome it launched earlier lost its page: find it with `ps -axo pid,lstart,command | grep mcp-chrome`, check its start time matches this run's first navigate, and kill that pid only. Keep `$RUN/evidence/`; delete `$RUN/harness/` only when asked.

## Features

The map is `features/README.md`; add a file there for every new thing a person can see.
