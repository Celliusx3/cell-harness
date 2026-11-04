# 02 The steps line names what runs, and folds when the reply starts

**Status:** done

**What to build.**

- `frontend/components/conversation/turnProgress.ts`: `progressOf(rows, items, openTurn, sending)` returns `starting` while the turn shows nothing, which is when the Thinking row shows. It returns `{ kind: "running"; tool: string }` while a tool call has no result, and `writing` while the turn's newest item is reply text. Between steps it returns `thinking`.
- `frontend/components/conversation/turnRows.ts`: a turn's steps keep one key, so opening them survives the reply starting.
- `frontend/components/conversation/Activity.tsx` is rebuilt on `TraceCollapsible`. While live it shows a spinner and "Running file list · 2 tools", or "Thinking · 2 tools" between steps. Once the reply streams or the turn ends, it folds to "Used 2 tools", with "· 17 failed" when tools failed. If you opened it, it stays open.
- `frontend/components/conversation/ToolCard.tsx` shows a spinner while running, a check when done, and a warning when failed. Its name is `humanise`d: the server in grey, then the label.
- `frontend/components/conversation/Timeline.tsx` passes the open turn's progress to its `Activity`.

**Checks.**

- `npm run typecheck` and `npm run build` in `frontend/` pass. `make lint` passes.
- By hand, with the drive-cell-harness skill: ask for something that calls two tools. While the first runs, the line reads "Running <its label> · 1 tool" and its card has a spinner.
- By hand: between the two calls, the line reads "Thinking · 2 tools", and both cards have a check.
- By hand: when the reply streams, the steps fold to "Used 2 tools", and the reply's caret blinks.
- By hand: in a turn where a tool fails, its card shows a warning and the reason, and the folded line ends "· 1 failed".
- By hand: open the steps while the turn runs. They stay open after the reply starts.

**Blocked by.** 01
