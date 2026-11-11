# 01 · A reply shows its turn's usage on hover or tap

**Status.** done

**What to build.** The frontend `Usage` type gains `cached_input_tokens: number | null`. A new pure file adds up one turn's `AssistantItem` usages under the strict rules. A step without usage means no figures. Cache figures show only when every step reported them. It also formats counts (48.2k, 1.2M) and the hit rate. Each ended turn's answer block shows that line on hover, and on tap on touch screens.

Files: `frontend/lib/types.ts`, a new `frontend/components/conversation/usage.ts`, a new `ReplyUsage.tsx`, and `Timeline.tsx` (and `turnRows.ts` if the answer row needs the turn's items or its ended state).

**Checks.**

- Drive the chat with `drive-cell-harness`. A fake model reports `prompt_tokens: 10339`, `cached_tokens: 10318`, `completion_tokens: 40` on each of two steps. Hovering the answer shows "20.7k in · 80 out · 20.6k cached (100%)".
- With a fake model that reports no `prompt_tokens_details`: the line reads "… · cache not reported".
- With a fake model that reports no usage on one step: the line reads "usage not reported".
- While the turn is still running, hovering shows no line.
- A reload shows the same line. At phone width a tap shows it.
- `npm run typecheck`, `make lint` and `make test` stay green.

**Blocked by.** none
