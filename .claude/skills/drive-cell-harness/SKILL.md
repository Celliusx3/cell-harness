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
cd backend && uv sync --quiet && cd ..
[ -d frontend/node_modules ] || (cd frontend && npm ci --silent)
cd backend && HARNESS_SESSIONS__ROOT="$RUN/harness/sessions" \
  HARNESS_APPROVAL__GRANTS_PATH="$RUN/harness/approvals.json" \
  HARNESS_TELEGRAM__BOT_TOKEN="" HARNESS_DISCORD__BOT_TOKEN="" HARNESS_WEB__PUBLIC_URL="" \
  uv run uvicorn harness.web.server:create_web_app --factory --host 127.0.0.1 --port 4996 \
  > "$RUN/backend.log" 2>&1 &
echo $! > "$RUN/backend.pid"; cd ..
cd frontend && BACKEND_PORT=4996 npx next dev -p 4997 > "$RUN/frontend.log" 2>&1 &
echo $! > "$RUN/frontend.pid"; cd ..
```

Run both with the Bash tool's `run_in_background`, or keep the `&` and the pid files. Ready when `curl -s localhost:4996/api/conversations` prints a JSON list and `curl -s -o /dev/null -w '%{http_code}' localhost:4997` prints `200`. The backend connects every MCP server in `backend/config.json` at startup; the first start of a `uv run --project ../mcp-servers/...` server installs it, so allow a minute.

Why each variable: the sessions root and grants file keep the person's `~/.harness` untouched, and helper logs land beside the sessions root (`$RUN/harness/helpers`). The bot tokens are blanked because `backend/config.local.json` holds live ones; a copy with them answers the person's real Telegram and Discord chats.

## Doctor

```sh
lsof -nP -iTCP:4996 -iTCP:4997 -sTCP:LISTEN
grep -E "channel registered|ERROR|connected" "$RUN/backend.log" | tail
```

Both ports must belong to the pids in `$RUN/*.pid`. The log must say `web channel registered (pull)` and must not say `telegram channel registered`. A port held by another process is the person's own copy: pick other ports, never kill it.

Check which model this copy talks to before blaming the code: `backend/config.local.json` can override `llm.base_url` (for example LM Studio on `localhost:1234`). For LM Studio, `~/.lmstudio/bin/lms ps` shows the loaded `CONTEXT` and `PARALLEL`; a request over the context fails as "Context length exceeded", and requests running at once share that context, so with `PARALLEL` above 1 they fail together as "failed to decode". Load with `lms load <model> --context-length 16384 --parallel 1` to have LM Studio queue them.

## Drive

Load the browser tools with ToolSearch (`select:mcp__plugin_everything-claude-code_playwright__browser_navigate,...browser_snapshot,...browser_type,...browser_click,...browser_take_screenshot,...browser_wait_for,...browser_close`). Then:

1. `browser_navigate` to `http://localhost:4997`.
2. `browser_snapshot`, find the textbox with placeholder "Send a message", `browser_type` the prompt into it, `browser_click` the button labelled "Send".
3. The URL becomes `/c/<conversation id>`. While a turn runs, the Stop button (label "Stop") shows and tool cards say "running…"; when it ends they say "done" or an error code.
4. Click a tool card's name (for example `run_subagent`) to open it: its arguments and its result appear under it.
5. An approval card offers "Allow once", "Allow for this conversation", "Always allow" and "Deny".

Handles: placeholder "Send a message", labels "Send", "Stop", "New conversation", "Skills", "Approvals". Never click by coordinates.

## Evidence

Under `$RUN/evidence/`: a `browser_take_screenshot` after the action and after the turn ends (the tool may only write inside the folder Claude Code was started in, so give it a bare file name and `mv` the file into `$RUN/evidence/` at once; its snapshots land in that folder's `.playwright-mcp/`, delete the ones this run made), the conversation as stored (`curl -s localhost:4996/api/conversations/<id> > $RUN/evidence/conversation.json`), and any side effect the feature promises, such as files under `$RUN/harness/subagents/`. Quote the model's answer from the stored conversation, not from memory.

## Cleanup

```sh
kill "$(cat "$RUN/backend.pid")" "$(cat "$RUN/frontend.pid")"
```

`uv run` and `npx` start children that hold the ports: also kill the pids `lsof -nP -iTCP:4996 -iTCP:4997 -sTCP:LISTEN` shows. Then `browser_close`. Kill only these pids, never by name. If the browser tool says "Browser is already in use", the headless Chrome it launched earlier lost its page: find it with `ps -axo pid,lstart,command | grep mcp-chrome`, check its start time matches this run's first navigate, and kill that pid only. Keep `$RUN/evidence/`; delete `$RUN/harness/` only when asked.

## Features

The map is `features/README.md`; add a file there for every new thing a person can see.
