# MCP Apps — how a tool result gets a UI

Research behind insertion 6, and the choices it forced. The status paragraph in
[CLAUDE.md](../CLAUDE.md) is the summary; this is the reasoning.

## 1. What "MCP with UI" is in 2026

**MCP Apps** — [SEP-1865](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp),
extension id `io.modelcontextprotocol/ui`, Final since 2026-01-26; the
[2026-07-28 spec](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)
formalises the extensions framework it rides on. It unified
[MCP-UI](https://mcpui.dev/) (Shopify / idosal) and OpenAI's Apps SDK. Hosts
shipping it: Claude.ai and Desktop, ChatGPT, VS Code, Goose, Postman, MCPJam,
the Vercel AI SDK, assistant-ui. The full contract is in
[modelcontextprotocol/ext-apps](https://github.com/modelcontextprotocol/ext-apps).

The shape, in five lines:

- A tool declares `_meta.ui.resourceUri = "ui://<server>/<name>"` (and may
  declare `visibility: ["model" | "app"]`).
- The UI is a **predeclared resource**: `resources/read` on that URI returns one
  self-contained HTML document, `mimeType: "text/html;profile=mcp-app"`, with
  optional `_meta.ui.csp.{connectDomains,resourceDomains,frameDomains}`.
- The client negotiates it in `initialize`:
  `capabilities.extensions["io.modelcontextprotocol/ui"] = {"mimeTypes": [...]}`.
  A server should degrade to text for a client that did not.
- The host renders the HTML in an iframe whose origin differs from the host's,
  under a CSP that defaults to inline script and style, `data:` images, and no
  network.
- View and host speak **JSON-RPC over `postMessage`**: `ui/initialize` →
  `ui/notifications/initialized` → host sends `ui/notifications/tool-input`
  then `ui/notifications/tool-result {content, structuredContent, isError}`;
  afterwards the view may send `tools/call`, `ui/open-link`, `ui/message`,
  `ui/update-model-context`, `ui/notifications/size-changed`,
  `ui/request-display-mode`.

Why predeclared rather than inline HTML in the result: the host can prefetch,
cache and review the template, and the template is separate from the data.

## 2. What the SDKs already do

- **Python `mcp` 2.1.1 — the version every `mcp-servers/*` project pins — has
  MCP Apps in core.** Server: `mcp.server.apps.Apps` (`@apps.tool(resource_uri=…)`,
  `apps.add_html_resource(uri, html, csp=…)`, `MCPServer(…, extensions=[apps])`,
  `client_supports_apps(ctx)`). Client: `Client(…, extensions=[advertise(EXTENSION_ID, {"mimeTypes": [APP_MIME_TYPE]})])`,
  `tool.meta["ui"]["resourceUri"]`, `client.read_resource(uri)`. The SDK's own
  `examples/stories/apps/` is the whole loop in two files. `tests/mcp_stub.py`
  uses exactly this to prove our negotiation over real stdio.
- **TypeScript `@modelcontextprotocol/ext-apps` 2.0.0** ships the view SDK
  (`App`), the host SDK (`AppBridge`, `PostMessageTransport`), and server
  helpers. `AppBridge(null, …)` with manual `oncalltool` / `onsizechange` /
  `onopenlink` is the host shape for a browser that does *not* hold the MCP
  client — ours does not; the harness does.

## 3. The public target

Every example server in ext-apps is on npm as `@modelcontextprotocol/server-*`
with a `--stdio` flag, so the harness runs one from `config.json` with no code:

```json
"sysmon": { "command": "npx", "args": ["-y", "--silent", "@modelcontextprotocol/server-system-monitor", "--stdio"] }
```

`system-monitor` was chosen because one server exercises every path:
`get-system-info` (model-facing, bound to `ui://system-monitor/mcp-app.html`,
data in `structuredContent`) renders a dashboard, and the view then polls
`poll-system-stats` — `_meta.ui = {visibility: ["app"]}`, **no `resourceUri`** —
through `tools/call` every second. Its resource declares no CSP; the HTML is one
inline module script, 428 KB. Needs Node on `PATH`; the first start downloads.

Two things it exposed here: every public app names its tools in kebab-case
(`get-system-info`), which `mcp/tool.py` used to *drop*; and nothing yet hides an
app-only tool from the model.

## 4. How real hosts handle what the view sends

Where an app's `tools/call` goes, and what stands in its way:

| Host | Where the call goes | Checks | Through the model's tool layer? |
|---|---|---|---|
| **VS Code** (`mcpToolCallUI.ts`) | `McpTool.call()` → server; the model's path is a separate wrapper (`McpToolImplementation`, with confirmation) over the same `McpTool` | same server; `visibility` includes `app` | no |
| **Openwork** (`apps/server/src/mcp-app-host.ts`; browser + backend-held MCP, our shape) | dedicated backend fn → `client.callTool()` → server, raw result | live *launch* (a real tool call in a real session, expires); same server; `visibility`; tool bound to another app refused; workspace deny-policy by name at the MCP layer; approval unless `readOnlyHint`; 1 MiB cap | no |
| **Vercel AI SDK** | host callback → their backend | deny-by-default allowlist | no |
| **MCPJam** | host callback → server | model-only rejected; lifecycle shown | no |
| **ChatGPT** (Apps SDK reference) | `window.openai.callTool` "mirrors model-initiated calls" → server | tool opts in (`widgetAccessible`, default false; now `_meta.ui.visibility`) | no |
| **ext-apps basic-host** | `client.callTool()` | none | no |


| | view `tools/call` | `ui/message` | sandbox |
|---|---|---|---|
| **VS Code** (hand-rolled) | same server only, visibility-gated, no consent prompt, **not** in the chat log | prefills the composer (only if empty); the person sends | webview |
| **Vercel AI SDK** (hand-rolled) | deny-by-default allowlist, forwarded to their backend | handler | double iframe, inner `allow-scripts allow-forms` |
| **MCPJam** (official `AppBridge`) | model-only rejected; tracked as `{callId}:app-tool:{n}` with running/ok/error | sends as the user | proxy |

The common logic, which is what this insertion mirrors: a view's call goes
through the host's normal tool path, is scoped to the app's own server, asks no
consent, and is not part of the conversation the model sees.

## 5. Choices made here

- **Official `AppBridge`, not a hand-rolled host.** VS Code and Vercel hand-roll
  because they are platforms that cannot take the peer dependencies; MCPJam and
  the reference host use `AppBridge`. The public apps are built with the
  official `App` SDK, which does the full handshake (`hostContext`,
  `request-display-mode`, host-context changes) — the bridge answers all of it
  correctly for the price of `@modelcontextprotocol/{core,client}` and `zod`.
- **The binding rides the `tool/result` event as a new field, not a new block.**
  `ToolUi(server, resource_uri, data)` on `Ok` and on `ToolResultEvent`. The
  model path — `content`, the adapter, `render_text`, `tools_selected()` —
  is untouched; `derive.py` reads only `message`. `data` is the result's
  `structuredContent`, logged beside the reference because it is what the view
  draws and a reloaded conversation must draw the same thing.
- **`resources/read` is one more command on the store's loop.** `_Read` beside
  `_Call`, same owner task, same timeout, same error mapping — the anyio
  task-affinity constraint in `store.py` applies to every request kind.
- **Two browser endpoints, `harness/web/routes/mcp.py`.**
  `GET /api/mcp/{server}/resources?uri=` returns the HTML and a CSP string the
  harness composed (spec defaults, widened only by the https origins the
  resource declared — values are parsed as URLs and only their origin kept).
  `POST /api/mcp/{server}/tools/{name}` **proxies** the call to the app's own
  server — by the server's name, resolved from the server's published list,
  the `CallToolResult` returned verbatim (`_meta`, image blocks and all). Not
  the dispatcher: that is the model's and a script's path, with a menu to
  offer and refusals to give, and an app has neither. A first version went
  through the dispatcher and the model-shaped `Ok`; it re-spelt the name,
  serialised the arguments to parse them again, and flattened the result to
  text — five steps to arrive where the store already was. Not a session
  event: nothing the model sees results from it.
- **What guards an app's call, and where.** The survey below is unanimous:
  nobody routes it through the model's tool layer, and the guards sit at the
  MCP layer. Ours: the path's server is the only one reachable (a native tool
  is not in its list — 404 that names nothing else); `_meta.ui.visibility` must
  include `app` (403); a tool bound to a *different* app's resource is refused
  (403, Openwork's rule — the request carries the app's own `resource_uri`).
  Not yet: approval for tools without `readOnlyHint` (Openwork, Vercel's
  allowlist, ChatGPT's opt-in) and a result size cap — with auth, below.
- **Hyphens are mapped, not dropped.** `namespaced()` spells `get-system-info`
  as `sysmon__get_system_info` for the model and code mode; `execute` calls the
  server by the published name. Two tools that map to one name keep the first.
- **Single srcdoc iframe, `sandbox="allow-scripts allow-forms"`.** No
  `allow-same-origin`, so the view runs on an opaque origin — the spec's
  requirement that host and app differ, and exactly Vercel's inner iframe. The
  CSP is a `<meta http-equiv>` injected into the document, since a `srcdoc` has
  no headers. The bridge connects *before* `srcdoc` is set, so the listener is
  armed before the view's script runs; `contentWindow` keeps its identity
  across the navigation.
- **The `McpApp` effect keys on the app's identity, not the item.** The timeline
  rebuilds every item on every event; remounting would restart the app.

## 6. The same app in a chat that cannot render it

Telegram and Discord cannot render HTML in a message; what they can carry is a
**link**. Telegram's own answer is the Mini App: a `web_app` button that opens
a URL inside Telegram, with `window.Telegram.WebApp` as the page's bridge. So an
MCP App reaches a chat as a page the harness serves:

- `/apps/{conversation}/{call}` (`frontend/app/apps/`) renders one tool call's
  app on its own — no sidebar, the whole viewport — from the same log as the
  conversation page. The chat pages moved under a `(chat)` route group so the
  sidebar is theirs alone.
- `Pushing.send_link(chat_id, text, url)` joins `send_message` and
  `send_typing` on the seam, with the same contract as typing: a button where
  the platform has one, the URL as text where it does not. Telegram sends a
  `web_app` button for `https://` and a `url` button otherwise (Telegram's
  rule, not ours); Discord a link button. The gateway's `_deliver` sends it
  when a `tool/result` with `ui` lands — named for the tool, before the prose.
- The browser card gets an "Open app" link to the same URL — no inline
  iframe in the timeline, so all three channels open an app the same way and a
  long conversation never carries a dozen live iframes.
- `web.public_url` in `config.json` is where that link points. **Empty by
  default, meaning no link is sent** — the frontend port lives in the
  `Makefile` alone, and a phone cannot open `localhost` anyway. Measured
  against the Bot API: a `web_app` button accepts only `https://`; a `url`
  button accepts `http://` but refuses `localhost` ("Wrong HTTP URL") while
  accepting `127.0.0.1` and any real host. So: a tunnel's `https://` URL for
  the Mini App sheet, `http://127.0.0.1:4897` for Discord on this machine.
- A link is best-effort; a reply is not. The gateway logs a refused link and
  moves on: raising would abort delivery with the cursor unadvanced, and the
  next turn would replay the same event into the same refusal, forever — a
  poison pill the first version had with its `localhost` default.

**Do not tunnel yet.** The harness binds `127.0.0.1` with no authentication,
because the browser is local. A public URL exposes every route — reading any
conversation, sending messages, calling tools on your servers — not just the
app page. The next step, before any tunnel: verify Telegram's `initData`
(an HMAC over the bot token that the Mini App page can present) and require it
on the routes the app page uses; Discord and a plain browser link need a
signed, expiring token instead. That is the first authenticated route this
project will have, and it is its own piece of work.

## 7. Deferred, deliberately

- `_meta.ui.visibility: ["app"]` — keeping app-only tools out of
  `list_functions` and the model. Today `sysmon__poll_system_stats` is visible;
  its description says "App-only".
- `ui/message` (VS Code's composer-prefill is the consent-preserving choice),
  `ui/update-model-context`, fullscreen display mode, `resources/read` from the
  view.
- The double-iframe sandbox proxy on a second origin — needed only by views
  that want `allow-same-origin` (the Cesium map uses `document.write`).
- Images in tool results still reach the view as the log's placeholder text,
  so a view that draws `content[].type == "image"` (ext-apps' `qr-server`) has
  nothing to draw. Presentation bytes that must not enter the log are the
  next design question, not this one.
- A UI for a script's sub-calls: `sub:N` is never logged.
- Resource caching: the spec allows prefetch; the browser reads on every render.
