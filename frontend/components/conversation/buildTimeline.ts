import { TimelineDraft } from "@/components/conversation/timelineDraft";
import type { Timeline } from "@/components/conversation/timelineItems";
import { humanise } from "@/lib/toolName";
import type { SessionEvent } from "@/lib/types";

/** Session events after the last clear -> what the screen shows. */

export function buildTimeline(events: SessionEvent[]): Timeline {
  const draft = new TimelineDraft();
  const start = events.map((event) => event.type).lastIndexOf("chat/cleared") + 1;
  const lastReports = lastReportOfEachTicket(events);

  for (const [index, event] of events.entries()) {
    if (index < start) continue;
    if ("turn" in event && event.turn !== null) draft.rememberTurn(event.turn);

    switch (event.type) {
      case "user/message":
        draft.onUserMessage({
          key: `u${index}`,
          turn: event.turn,
          content: event.message.content,
          files: event.files,
        });
        break;

      case "bot/message":
        draft.onUserMessage({
          key: `u${index}`,
          turn: event.turn,
          content: `Message from ${event.message.from_name}:\n\n${event.message.text}`,
          files: [],
        });
        break;

      case "ticket/report":
        draft.addNotice({
          key: `r${index}`,
          turn: event.turn,
          tone: "note",
          text: `${event.report.title}: ${event.report.state}`,
        });
        if (event.report.question !== null) {
          draft.onTicketQuestion({
            kind: "ticketQuestion",
            key: `q${index}`,
            turn: event.turn,
            ticketId: event.report.ticket_id,
            question: event.report.question,
            ask: event.report.ask,
            options: event.report.options ?? [],
            secretName: event.report.secret_name,
            approvalCallId: event.report.approval_call_id,
            latest: lastReports.get(event.report.ticket_id) === index,
          });
        }
        break;

      case "schedule/reminder":
        draft.onScheduled(`s${index}`, event.turn, event.reminders);
        break;

      case "schedule/change":
        draft.onScheduleChange(`c${index}`, event.change);
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
          files: event.files,
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

      case "approval/mode":
        draft.onModeSwitch(`m${index}`, event.mode);
        break;

      case "bot/instructions":
        draft.onBotInstructions(`b${index}`, event.bot_id ?? null, event.name);
        break;

      case "group/members":
        draft.onGroupMembers();
        break;

      case "turn/start":
        draft.onTurnStart(event.turn, event.bot_id ?? null);
        break;

      case "step/start":
      case "step/end":
      case "server/instructions":
      case "chat/cleared":
        break;
    }
  }

  return draft.toTimeline();
}

/** The index of each ticket's last report among `events`. */
function lastReportOfEachTicket(events: SessionEvent[]): ReadonlyMap<string, number> {
  return new Map(
    events.flatMap((event, index): [string, number][] =>
      event.type === "ticket/report" ? [[event.report.ticket_id, index]] : [],
    ),
  );
}
