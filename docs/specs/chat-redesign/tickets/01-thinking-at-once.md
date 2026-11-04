# 01 Your message and "Thinking" show the moment you press send

**Status:** done

**What to build.**

- `npx shadcn add trace` writes `frontend/components/ui/trace.tsx` and `collapsible.tsx` on Base UI. They are generated, so nothing edits them.
- `frontend/components/conversation/useConversation.ts` gains `sending: string | null`, the prompt pressed but not yet in the log. `send` sets it before the request. A `user/message` event or a failed send clears it.
- `frontend/components/conversation/turnProgress.ts` is new. `progressOf(rows, openTurn, sending)` returns `{ kind: "thinking" } | null` for now: thinking while a turn is open or a send is in flight and the open turn shows nothing yet.
- `frontend/components/conversation/ThinkingRow.tsx` is new. It is a `TraceLine` with status `running` and the title "Thinking".
- `frontend/components/conversation/Timeline.tsx` draws the `sending` prompt as your bubble, then the bot's avatar and name over a `ThinkingRow`. It takes the chat's own bot as `host: Speaker | null`, and an answer row with no speaker uses it. So every reply in a bot's own chat carries the name and avatar.
- `frontend/app/(chat)/c/[id]/page.tsx` passes `host` (the bot, or null in a group) and `sending`.

**Checks.**

- `npm run typecheck` and `npm run build` in `frontend/` pass. `make lint` passes.
- By hand, with the drive-cell-harness skill on a local model: send a message. A screenshot 100 ms after Enter shows your message, the bot's avatar and name, and "Thinking".
- By hand: when the reply arrives, it sits under the same avatar and name. No second name shows.
- By hand: stop the backend and send. Your message and "Thinking" go away, and the error shows.
- By hand: in a group's chat, send. "Thinking" shows with no name, and the answering bot's name shows when its turn starts.

**Blocked by.** none
