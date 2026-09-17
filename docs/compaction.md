# Compaction — phase 11

**cell-bot's largest gap.** History is the whole conversation on every request;
past enough turns it slows, costs, and finally the provider refuses it and the
turn dies. Compaction keeps a long conversation going by shrinking what the
model is *sent* — never what the log *holds*.

The shape is Claude Code's, with dsh's events:

- one **boundary**: older history is summarized into a single message the model
  reads instead;
- a continuous **prune** of old tool results before any summary — they are the
  bulk and the least re-readable;
- `usage` of the last reply as the size signal, so there is no tokenizer;
- a check **before every step**, mid-turn included, plus a **reactive net** when
  the provider refuses a request for its size;
- everything **appended** — `derive_messages()` honours the boundary, so the raw
  log still replays in full. This is only possible because phase 1 made the loop
  derive its history from the log rather than a list it kept.

## The events

Three, added to the closed `SessionEvent` union like `application/message` was
in phase 9 (`session/compaction.py`):

- `compaction/start { turn, trigger: auto|manual|overflow, tokens }` — a
  compaction is being attempted. `turn` is `null` for a manual one on an idle
  conversation (dsh's `turn: null`); `tokens` is the size that triggered it
  (Claude Code's `preTokens`).
- `compaction/end { turn, message, error }` — the attempt is over. `message` is
  exactly what the model reads from here on — logged verbatim, so the UI shows
  the same words. `message: null` with an `error` is an attempt that changed
  nothing, a fact about the conversation like a failed turn, and **not** a
  boundary.
- `compaction/prune { turn, call_ids }` — these results are cleared from the
  model's view.

Two events bracket a summary, not dsh's three: the summary rides on `end` the
way `usage` rides on `assistant/message`. A `compaction/start` a crash left
without an end is closed by `repair` with an `error` end — close, do not
truncate.

## How `derive_messages` honours them

`session/derive.py`, the one place model history is produced:

- the last `compaction/end` **with a message** is the boundary — derivation
  starts there, that message in the user role (where Claude Code and the phase-9
  guardrail both put injected context), nothing before it;
- the union of every `compaction/prune.call_ids` is the pruned set — a pruned
  `tool/result` renders as a placeholder (`PRUNED`), telling the model to call
  the tool again if it still needs it.

Everything else that folds the raw log — `Session.tools_selected()`, the hook
folds, `repair`, `pending_call` — reads it unchanged, so a pruned
`get_function_details` result keeps its tool callable, and the guardrail keeps
counting.

## The trigger

`Compactor.due` compares the context size against a line:

```
threshold = floor(context_tokens × 0.8)          # COMPACT_AT; dsh's ratio
used      = last assistant/message.usage.input_tokens + output_tokens
```

`context_tokens` is resolved once at startup (`create_web_app`):
`compaction.context_tokens` from config if set, else `context_length` read from
the endpoint's `GET /v1/models`, else unknown → proactive compaction off, one
warning, the reactive net alone. It is a cap on cost and latency, not a claim
about the model — the net covers a value set too high.

When due, before the request is built: prune if anything is prunable (no model
call — the next step's real `usage` says whether it was enough); else
summarize. `skill` results are never pruned and the most recent `PRUNE_KEEP = 3`
are kept.

## The reactive net

The adapter classifies a 4xx body it recognises as
`Failed(code=CONTEXT_WINDOW_EXCEEDED)`; the loop then compacts and retries the
step. Bounded: each recovery strictly shrinks the derived history, and a log
that is only a summary has nothing left, so a summary that cannot shrink further
fails the turn. Recognition is exact and fails closed — an unrecognised 400 is a
failed turn, never a compaction, because a generic refusal that meant a
malformed request would otherwise compact the wrong conversation.

## Skills survive

A loaded skill is behavioural guidance, not data: losing it degrades the agent
with no visible error. So the summary's `message` re-attaches the **last body
per skill loaded before the boundary**, found in both shapes — a `skill`
tool result, and a `/name` expansion inside a `user/message` (both open with
`<skill name="`). Claude Code re-attaches the last invocation of each skill;
this does the same, unbounded (ours are already bounded at load).

## Manual `/compact`

A run of its own (`RunStore.compact`), so the busy check, the SSE stream, the
flush-on-settle, and `stop` come for free, and every chat mapped to the
conversation follows it. On web it is `POST /api/conversations/{id}/compact` and
a header button; on Telegram and Discord it is `/compact`. The compactor refuses
out loud — `nothing to compact`, or a client request still unanswered — rather
than write an empty bracket; the route returns that as a 409.

## Endpoint evidence (probed 2026-09-16)

The two questions — where does the window come from, and can the overflow be
recognised — answered against the user's two endpoints:

| Model @ endpoint | streamed `usage` | window in `GET /v1/models` | overflow 4xx |
|---|---|---|---|
| gemma-4-e4b @ LM Studio | yes | no (only `/api/v0/models`: loaded 16384) | `{"error":"Context length exceeded"}` — recognised |
| glm-5.3 @ ilmu | yes | `context_length: 1000000` | generic `invalid_request` — not recognised |
| glm-5v-turbo @ ilmu | — | `200000` | generic — not recognised |
| glm-ocr @ ilmu | — | `32768` | `code: context_length_exceeded` — recognised |

So the window is discovered where reported (ilmu) and configured where not (LM
Studio), and the reactive net catches LM Studio and some ilmu models but is
never the mechanism. `GET /v1/models/{id}` is 404 on ilmu; the list carries the
field. Claude Code's own answers: a per-model table for the window, `usage` for
the size, a check before every request, and on "prompt too long" it does not
retry — it asks the person to `/compact`.
