import { display, type Invocation } from "@/lib/invocation";
import type { ContentBlock, SessionEvent, ToolCall, ToolUi, Usage } from "./types";

/**
 * Session events -> what the screen shows.
 *
 * **The one renderer.** It takes `SessionEvent[]` and cannot tell whether they
 * came from the snapshot or the live stream, which is what makes "a reloaded
 * conversation renders identically" true by construction rather than by keeping
 * two code paths in step.
 *
 * ## The doubling bug this file is shaped to avoid
 *
 * A reply arrives twice in the log, on purpose: as a run of `assistant/chunk`
 * events (kept so replay is token-faithful) and then as one `assistant/message`
 * (the assembled result). Render both and every answer appears twice.
 *
 * Worse, `assistant/chunk` carries the *whole* stream union — including the
 * `completed` terminal, which holds `full_text`. Treating every chunk as text to
 * append doubles the reply on its own, before `assistant/message` is even seen.
 *
 * So: accumulate **only** `kind: "text"` chunks, keyed by `(turn, step)`, and
 * *replace* the accumulation when `assistant/message` for that key arrives.
 */

export interface UserItem {
  kind: "user";
  key: string;
  turn: number;
  /** The whole message as logged and sent — for `/name`, that includes the skill. */
  content: string;
  /** Set when the message is a `/name` expansion: the short form to show. */
  invoked: Invocation | null;
}

export interface AssistantItem {
  kind: "assistant";
  key: string;
  turn: number;
  step: number;
  content: string;
  /** No `assistant/message` yet, so the text is still arriving. */
  streaming: boolean;
  /** Finalized from the prefix the user saw after a cancel, not a short answer. */
  interrupted: boolean;
  usage: Usage | null;
}

export interface ToolItem {
  kind: "tool";
  key: string;
  turn: number;
  step: number;
  call: ToolCall;
  /** The result's blocks — text carrying its `error: ` prefix if it failed,
   *  and any tools it made callable. Null while the call is running. */
  result: ContentBlock[] | null;
  /** The typed failure code, or null. Non-null means the card shows as failed. */
  error: string | null;
  /** The MCP App that draws this result, arriving with `tool/result`. */
  ui: ToolUi | null;
}

export interface NoticeItem {
  kind: "notice";
  key: string;
  turn: number;
  tone: "error" | "cancelled" | "note";
  text: string;
}

export type TimelineItem = UserItem | AssistantItem | ToolItem | NoticeItem;

export interface Timeline {
  items: TimelineItem[];
  /** True while the last turn is still open — no `turn/end` for it yet. */
  openTurn: number | null;
  /**
   * The opening message, for a header whose stored title is not there yet.
   *
   * The backend stamps `title` from the first user message at the first flush,
   * which lands *after* the create response returns — so a brand-new
   * conversation legitimately has an empty title for its first turn. The text is
   * already on screen, so showing "Untitled" would be withholding something we
   * have.
   */
  openingMessage: string | null;
}

export function buildTimeline(events: SessionEvent[]): Timeline {
  const items: TimelineItem[] = [];
  /** (turn, step) -> index in `items`, so a chunk can find its own bubble. */
  const assistantAt = new Map<string, number>();
  /** tool_call_id -> index in `items`, so a result can find its call. */
  const toolAt = new Map<string, number>();
  const closed = new Set<number>();
  let lastTurn: number | null = null;

  const stepKey = (turn: number, step: number) => `${turn}:${step}`;

  for (const [index, event] of events.entries()) {
    lastTurn = "turn" in event ? event.turn : lastTurn;

    switch (event.type) {
      case "user/message":
        items.push({
          kind: "user",
          key: `u${index}`,
          turn: event.turn,
          content: event.message.content,
          invoked: display(event.message.content),
        });
        break;

      case "application/message":
        // The harness's words, not the person's: a notice, never a bubble.
        items.push({
          kind: "notice",
          key: `n${index}`,
          turn: event.turn,
          tone: "note",
          text: event.message.content,
        });
        break;

      case "assistant/chunk": {
        const chunk = event.chunk;
        if (chunk.kind === "text") {
          const key = stepKey(event.turn, event.step);
          const at = assistantAt.get(key);
          if (at === undefined) {
            assistantAt.set(key, items.length);
            items.push({
              kind: "assistant",
              key: `a${key}`,
              turn: event.turn,
              step: event.step,
              content: chunk.text,
              streaming: true,
              interrupted: false,
              usage: null,
            });
          } else {
            const item = items[at] as AssistantItem;
            items[at] = { ...item, content: item.content + chunk.text };
          }
        } else if (chunk.kind === "failed") {
          // The provider gave up mid-stream. Distinct from `turn/end: failed`,
          // which is the turn's own conclusion, and this one carries the reason.
          items.push({
            kind: "notice",
            key: `f${index}`,
            turn: event.turn,
            tone: "error",
            text: chunk.reason,
          });
        }
        // `tool_call` and `completed` chunks are deliberately ignored:
        // `tool/call` and `assistant/message` are the durable statements of the
        // same facts, and `completed.full_text` is the reply again.
        break;
      }

      case "assistant/message": {
        const key = stepKey(event.turn, event.step);
        const at = assistantAt.get(key);
        const settled: AssistantItem = {
          kind: "assistant",
          key: `a${key}`,
          turn: event.turn,
          step: event.step,
          // Replaces the accumulation rather than adding to it.
          content: event.message.content,
          streaming: false,
          interrupted: event.interrupted,
          usage: event.usage,
        };
        if (at === undefined) {
          // A step that streamed no text — it went straight to tool calls.
          // Recorded anyway so `usage` is not lost; rendering skips empties.
          assistantAt.set(key, items.length);
          items.push(settled);
        } else {
          items[at] = settled;
        }
        break;
      }

      case "tool/call":
        toolAt.set(event.call.id, items.length);
        items.push({
          kind: "tool",
          key: `t${event.call.id}`,
          turn: event.turn,
          step: event.step,
          call: event.call,
          result: null,
          error: null,
          ui: null,
        });
        break;

      case "tool/result": {
        const at = toolAt.get(event.message.tool_call_id);
        if (at === undefined) break; // a result whose call predates this window
        const item = items[at] as ToolItem;
        items[at] = { ...item, result: event.message.content, error: event.error, ui: event.ui };
        break;
      }

      case "turn/end":
        closed.add(event.turn);
        if (event.reason === "cancelled") {
          items.push({
            kind: "notice",
            key: `e${index}`,
            turn: event.turn,
            tone: "cancelled",
            text: "Stopped.",
          });
        } else if (event.reason === "failed") {
          // A `failed` chunk above usually carries the detail; this is the
          // backstop for a turn that failed without one (a missing terminal).
          items.push({
            kind: "notice",
            key: `e${index}`,
            turn: event.turn,
            tone: "error",
            text: "This turn did not complete.",
          });
        }
        break;

      // Boundaries carry no content of their own. They matter to the log's
      // structure, not to what is on screen.
      case "turn/start":
      case "step/start":
      case "step/end":
        break;
    }
  }

  const opening = items.find((item) => item.kind === "user");
  return {
    items,
    openTurn: lastTurn !== null && !closed.has(lastTurn) ? lastTurn : null,
    openingMessage: opening ? opening.content : null,
  };
}
