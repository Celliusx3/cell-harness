import { TimelineDraft } from "@/components/conversation/timelineDraft";
import type { Timeline } from "@/components/conversation/timelineItems";
import { humanise } from "@/lib/toolName";
import type { SessionEvent } from "@/lib/types";

/** Session events -> what the screen shows. */

export function buildTimeline(events: SessionEvent[]): Timeline {
  const draft = new TimelineDraft();

  for (const [index, event] of events.entries()) {
    if ("turn" in event && event.turn !== null) draft.rememberTurn(event.turn);

    switch (event.type) {
      case "user/message":
        draft.onUserMessage(`u${index}`, event.turn, event.message.content);
        break;

      case "application/message":
        draft.addNotice({
          key: `n${index}`,
          turn: event.turn,
          tone: "note",
          text: event.message.content,
        });
        break;

      case "assistant/chunk": {
        const chunk = event.chunk;
        if (chunk.kind === "text") {
          draft.onAssistantText(event.turn, event.step, chunk.text);
        } else if (chunk.kind === "failed") {
          draft.addNotice({
            key: `f${index}`,
            turn: event.turn,
            tone: "error",
            text: chunk.reason,
          });
        }
        break;
      }

      case "assistant/message":
        draft.onAssistantMessage({
          turn: event.turn,
          step: event.step,
          content: event.message.content,
          interrupted: event.interrupted,
          usage: event.usage,
        });
        break;

      case "tool/call":
        draft.onToolCall(event.turn, event.step, event.call);
        break;

      case "tool/result":
        draft.onToolResult({
          callId: event.message.tool_call_id,
          result: event.message.content,
          error: event.error,
          ui: event.ui,
        });
        break;

      case "turn/end":
        draft.onTurnEnd(event.turn);
        if (event.reason === "cancelled") {
          draft.addNotice({
            key: `e${index}`,
            turn: event.turn,
            tone: "cancelled",
            text: "Stopped.",
          });
        } else if (event.reason === "failed") {
          draft.addNotice({
            key: `e${index}`,
            turn: event.turn,
            tone: "error",
            text: "This turn did not complete.",
          });
        }
        break;

      case "compaction/start":
        draft.onCompactionStart(`k${index}`, event.turn, event.tokens);
        break;

      case "compaction/end":
        draft.onCompactionEnd(
          event.message ? event.message.content : null,
          event.error,
        );
        break;

      case "compaction/prune":
        break;

      case "approval/grant":
        draft.addNotice({
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

  return draft.toTimeline();
}
