# Data the client holds — client tools

The first case is location. "What's near me?" needs coordinates only the
person's device has; the server has nothing to compute from. This note is the
prior art, the shape chosen, and why — the reasoning behind `tools/client/`,
`tools/native/location/`, `web/routes/client.py`, `channels/client.py` and
`Pushing.ask_client`.

## 1. The four shapes in the wild

| Shape | Who | Where the answer lands | When nobody can answer |
|---|---|---|---|
| **Ambient** — the client attaches location to every request | ChatGPT (IP-approximate, opt-in device location), Open WebUI `{{USER_LOCATION}}`, OpenAI's and Anthropic's `user_location` on web search, claude.ai on the web, ilmuchat (§6) | System prompt or tool config; never a tool result | No failure — the field is absent, and the model has to know to ask |
| **Blocking** — the tool awaits the client, correlated by an id | MCP `elicitation/create`, Claude Code `AskUserQuestion` / `canUseTool`, dsh `ask_user_question`, OpenClaw `node.invoke location.get`, **the Claude iOS/Android app's location tool** | The `tool_result`, and nothing else | MCP and the Agent SDK have no timeout ("pending indefinitely"); OpenClaw has `timeoutMs` and typed error codes; hermes-agent's `clarify` gives up after 10 minutes with a sentinel the model reads |
| **Continuation** — the turn ends; the answer starts the next | Vercel AI SDK client tools (`addToolOutput` → new POST), OpenAI Assistants `requires_action`, LangGraph `interrupt()`, AG-UI `outcome: interrupt` → `resume[]` | A persisted pending call, answered as an ordinary tool result later | Expiry is a state transition (`expiresAt`), not a hung socket |
| **Platform-native** — the chat's own prompt | Telegram `KeyboardButton.request_location`; Discord has no location primitive at all | An incoming *message* (`Message.location`), with no reference to what asked | The person may reply with anything else instead |

Three lessons carried over. The answer vocabulary is OpenClaw's — `lat`,
`lon`, accuracy in metres, and error codes rather than prose. "No client could
answer" must be a result the model can tell apart from "the person said no":
Claude Code's VS Code extension advertised elicitation and auto-declined every
request, and servers could not distinguish it from a human "No". And a tool
whose result a human produced is the same primitive whether the result is
coordinates or a decision — Vercel's `getLocation` and `askForConfirmation`
are one code path, LangChain's `respond` returns the human's words *as* the
tool's result — which is what lets one spine serve every datum.

## 2. A client tool is a declaration

**Vercel's logic, on our runtime.** In the Vercel AI SDK a tool declared
without an `execute` is a client tool: the server streams the call and
*stops*, the client produces the output however it can and posts it
(`addToolOutput`), and a new request resumes the model with it as the tool's
result. LangGraph's `interrupt`, OpenAI Assistants' `requires_action` and
AG-UI's interrupts are the same shape: the run ends at the ask, the pending
call is persisted, the answer starts the continuation. A new datum is a
declaration on the server and a handler in the browser. (The first cut here
blocked the tool in memory for two minutes instead — dsh's shape; it cost the
composer, restarts, and a "nobody answered" message to an empty room, and
was replaced on 2026-09-16.) Claude's mobile app is the same shape
from the product side — a set of device tools (Location & Maps, Calendar,
Reminders, Health, the share sheet) the model calls *"when Claude determines
that using one of these features would be helpful"*; the person *"sees cards
and reviews before taking action"*; permission is the device's, per tool
(While Using / Ask next time / Never); *"Claude only accesses the data
necessary for each specific request"* (support.claude.com 11869619, 11869629).

Here, a client tool is `ClientTool(name, description, args_model, data_model)`
and nothing more. Everything else is `tools/client/`, the same for every
datum:

- **The turn ends at the ask.** `ClientTools.definitions()` turns each
  declaration into a registered tool whose execute returns `Pending` — a
  third outcome beside `Ok` and `Failure`, so the dispatcher stays the one
  door and the loop never checks a tool's name. On `Pending` the loop writes
  no result and closes the turn with `turn/end {reason: "pending"}`. Nothing
  runs, nothing waits in memory, there is no timer. The card is on screen
  because the log holds an unanswered call; `runs.active()` is false, so the
  composer is free and Stop is hidden.
- **The answer opens the next turn.** `LoopAgent.resume(call_id, outcome)`
  opens a turn whose first event is the `tool/result` for the pending call;
  the request it builds carries `assistant(tool_calls) → tool(result)` — the
  sequence providers require — because `derive_messages` ignores turn
  boundaries. The model continues as if the tool had simply taken a while.
- **Typing instead skips it.** `LoopAgent.run()` first answers every
  unanswered call in the log as `SKIPPED` ("the user continued without
  answering this; do not ask again unless they return to it"), then opens the
  turn with the message. Not optional: a provider rejects a history with a
  call and no result — it is a 400 before the model sees it.
- **A pending turn is not a crash.** `repair()` leaves an unanswered call
  alone when its turn ended `pending`; every other unanswered call is still
  `INTERRUPTED_BY_CRASH`. That is why the reason is written down rather than
  inferred: repair and the screen both read it.
- **No expiry, and chats wait silently.** A late answer is still a current
  location, and "moved on" is detected by the person typing. On a chat the
  bot says nothing until the person acts: tap → answered, type → skipped,
  nothing → nothing. Telegram clears its keyboard on every reply, since any
  reply means the ask is over.
- **The four outcomes, one vocabulary.** What a client can answer is the
  spine's shape — `Shared[data] | Declined | Unavailable(reason)` — and what
  the model reads is decided once: shared data as JSON (what Vercel hands the
  model; what every MCP tool already returns), and three typed failures,
  `DECLINED`, `UNAVAILABLE`, and the loop's `SKIPPED`. The model recovers the
  same way from each — ask in words, or not at all — but the guardrail counts
  by code and a card reads them. A tool that *does* something on the device rather than reading it
  (Claude's share sheet, "add to calendar") is the same shape with an empty
  `data_model`; documented, not built.
- **A tool learns its call id.** `execute(args, context)` with
  `ToolContext(call_id, progress)`, built by the dispatcher from the
  `ToolCall` it holds. A tool whose answer arrives from outside the process
  must know which call it is; nothing else needed to, which is why the
  context arrived with its first consumer and not before. dsh's tools take
  `exec`, FastMCP's take `ctx`.
- **Which call may be answered is read off the log.** `pending_call(session,
  names)`: the current turn's unanswered call to a client tool. The log is
  what the client was shown, so the log decides — `ClientToolService`
  accepts by call id (the browser) or by tool name (a chat) through the same
  checks, and hands back what the resumed turn opens with; the route and
  `ChatAnswers` then call `RunStore.resume` (a chat's through the gateway, so
  the reply is delivered).

**The acceptance criterion.** A second datum is `tools/native/<x>/{models,
tool}.py`, one entry in `CLIENT_TOOLS` (`web/agent.py`), and one entry in the
browser's handler map — and no line in `tools/client/`, `routes/client.py`,
`channels/client.py`, `Replies`, the loop or the run store. `test_client_tools.py` proves the spine on
a throwaway declaration so that stays true without a second real tool.

## 3. One request, three deliveries

The ask is delivered where app links are: `Replies.deliver` watches the run's
events for a chat, and a `tool/call` to a client tool becomes
`transport.ask_client(chat_id, request, url)` — the platform is a client and
fulfils the request by tool name, as the browser's map does.

| Client | The ask | The answer |
|---|---|---|
| Browser | `CLIENT_TOOLS[name]` — Vercel's `onToolCall` as a lookup. `LocationRequest` replaces the tool card when the call has no result. Permission is the browser's own tri-state read off `permissions.query`, the way Claude's app reads the device's: granted → shares at once; blocked → `unavailable` at once; undecided → two buttons, the prompt behind a click | `POST /api/conversations/{id}/calls/{call_id}/output` — `addToolOutput`. Refused unless the call is the one pending (404), the body fits that tool's declaration (422), and no turn is running (409). The output opens the turn that carries it |
| Telegram | Its own prompt where it has one: for a location, a reply keyboard with one `request_location` button, private chats only. Any other client tool: a link to `/answer/{id}/{call}` | The pin arrives as a location message; `ChatAnswers` maps chat → conversation → live run → pending call and validates the body like the route does. A pin with nothing waiting is sent as text: a person who shares one unprompted meant it |
| Discord | No device prompts exist, so always the link — the browser card on a page of its own, dispatched by the same map. No `public_url` → the chat is told so in words | The page posts to the same route |

Both `ask_client` and the app link are best-effort: a prompt that could not be
sent times out into a result the model can act on, whereas aborting delivery
would replay the same event into the same refusal on every turn.

## 4. What the model was told, and why

The description names the trigger words — "near me", "nearby", "around here" —
because a model not told when to reach for the tool answers "I don't know where
you are" instead of asking. It also says to find a places search with
`list_functions` rather than guess, because the first live run did guess:
handed coordinates and told to "pass them to a places search", a model wrote a
script calling `places__search`, a name that does not exist, and reported the
failure as its answer. Prompt text is code; the failure is recorded beside the
wording that fixed it.

## 5. What is kept, and where

Nothing is kept in memory, at any point: the pending call is the `tool/call`
in the conversation's JSONL, and the answer is the `tool/result` that opens
the next turn — durable, and resent to the model on every later turn of that
conversation, like every tool result. That is forced by "model-visible means logged": a result the
model read has to be reconstructable. The browser rounds to three decimals
(~100 m) before posting, so the record holds less than a raw fix — enough for
"near me". Nothing is kept in the browser, and nothing outside the log.

Claude Code keeps the answer to `AskUserQuestion` the same way, in the session
transcript. ilmuchat keeps nothing (§6). Whether Anthropic's app keeps the
coordinates inside the stored conversation is undocumented: the privacy
policy says device location is processed "when you choose to share your
location with Claude", and conversations are retained, but not whether the
fix is in them (privacy.claude.com 10301952, 11186740). The choice here —
logged, rounded — was made on 2026-09-16 with that known.

## 6. Not taken: the ambient design, as ilmuchat ships it

ilmuchat (`~/Desktop/ai-labs/ilmuchat`, a production chat product) never asks
mid-turn. Three layers instead: every request carries a coarse location
resolved from the IP (Cloudflare headers, then a local MaxMind database),
rendered into the system prompt as "The user's location is Kuala Lumpur…";
precise coordinates ride the request only when the browser permission is
already `granted` (`maximumAge: 0`, never persisted — "Request-scoped only"),
and reach tools but never the prompt, snapped to ~1 km for search; and when a
tool wanted precise coordinates and had none, it answers from the IP estimate
and emits a side-channel `location_prompt` SSE that the UI turns into a
"Use precise location" action which regenerates the turn. The model is told it
must never ask the user for their city. Safari gets its own module, because
`permissions.query` always answers `prompt` there.

It is the right shape for a consumer product with IP-locatable requests and a
"never make the user work" rule. It is not on demand, it needs infrastructure
this harness does not have, and it cannot generalise to data an IP cannot give
— a contact, a photo. One line of it was taken: precise coordinates need not be
kept precise.

## 7. Not built

- **Ambient timezone / locale.** dsh attaches `clientTimeZone` to every
  prompt and a `time-context` plugin injects it per step. Worth its own note
  when a date question goes wrong. It would be a session event on the user
  message, additive to this design, not a change to it.
- **A second client tool.** Whichever comes first — a contact (Telegram's
  `request_contact` is the exact twin of `request_location`), a photo (needs
  image content in messages first), a question (dsh's `ask_user_question`,
  whose schema and label validation are the shape to copy) — it is one
  declaration and one handler. A tool without a browser permission of its own
  will need an app-level per-tool setting for Claude's tri-state; that day, not
  this one.
