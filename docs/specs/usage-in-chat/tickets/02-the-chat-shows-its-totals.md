# 02 · The chat's header shows its totals

**Status.** done

**What to build.** `usage.ts` gains the chat's totals under the lenient rules. It adds every `AssistantItem` after the last clear. A missing cache figure counts as 0, and a missing usage adds nothing. A figure no step reported reads "not reported". `ChatHeader` shows the totals on the line under the bot's name, beside the chat's state. PHASES.md records the insertion, and the spec's last check closes #62.

Files: `frontend/components/conversation/usage.ts`, `ChatHeader.tsx`, the page or component that renders `ChatHeader`, and `PHASES.md`.

**Checks.**

- Drive two turns on the cached fake model with `drive-cell-harness`. The header's input, output and cached totals equal the sum of both answers' lines. Its hit rate is that of the sums.
- After one more turn on a model without cache figures: the header's hit rate falls, and does not read "not reported".
- A fresh chat shows no totals. After a clear, the header shows no totals.
- A turn that used `run_subagent` adds only the bot's own steps.
- A reload shows the same totals.
- `npm run typecheck`, `make lint` and `make test` stay green.

**Blocked by.** 01
