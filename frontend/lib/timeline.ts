import { display, type Invocation } from "@/lib/invocation";
import { humanise } from "@/lib/toolName";
import type {
  ContentBlock,
  SessionEvent,
  ToolCall,
  ToolUi,
  Usage,
} from "./types";

/** Session events -> what the screen shows. */

export type {
  AssistantItem,
  CompactionItem,
  NoticeItem,
  Timeline,
  TimelineItem,
  ToolItem,
  UserItem,
} from "@/lib/timeline-items";
import type {
  AssistantItem,
  CompactionItem,
  NoticeItem,
  Timeline,
  TimelineItem,
  ToolItem,
  UserItem,
} from "@/lib/timeline-items";

export function buildTimeline(events: SessionEvent[]): Timeline {
  const items: TimelineItem[] = [];
  const assistantAt = new Map<string, number>();
  const toolAt = new Map<string, number>();
  const closed = new Set<number>();
  let compactionAt: number | null = null;
  let lastTurn: number | null = null;

  const stepKey = (turn: number, step: number) => `${turn}:${step}`;

  for (const [index, event] of events.entries()) {
    if ("turn" in event && event.turn !== null) lastTurn = event.turn;

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
          items.push({
            kind: "notice",
            key: `f${index}`,
            turn: event.turn,
            tone: "error",
            text: chunk.reason,
          });
        }
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
          content: event.message.content,
          streaming: false,
          interrupted: event.interrupted,
          usage: event.usage,
        };
        if (at === undefined) {
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
        if (at === undefined) break;
        const item = items[at] as ToolItem;
        items[at] = {
          ...item,
          result: event.message.content,
          error: event.error,
          ui: event.ui,
        };
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
          items.push({
            kind: "notice",
            key: `e${index}`,
            turn: event.turn,
            tone: "error",
            text: "This turn did not complete.",
          });
        }
        break;

      case "compaction/start":
        compactionAt = items.length;
        items.push({
          kind: "compaction",
          key: `k${index}`,
          turn: event.turn,
          tokens: event.tokens,
          summary: null,
          error: null,
          pending: true,
        });
        break;

      case "compaction/end": {
        if (compactionAt !== null) {
          const item = items[compactionAt] as CompactionItem;
          items[compactionAt] = {
            ...item,
            summary: event.message ? event.message.content : null,
            error: event.error,
            pending: false,
          };
          compactionAt = null;
        }
        break;
      }

      case "compaction/prune":
        break;

      case "approval/grant":
        items.push({
          kind: "notice",
          key: `g${index}`,
          turn: event.turn,
          tone: "note",
          text: `${humanise(event.tool).label} will run without asking in this conversation.`,
        });
        break;

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
