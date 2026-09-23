/** The timeline under construction: the items so far, and where the open ones sit. */

import { display } from "@/components/conversation/invocation";
import type {
  NoticeItem,
  Timeline,
  TimelineItem,
} from "@/components/conversation/timelineItems";
import type { ContentBlock, ToolCall, ToolUi, Usage } from "@/lib/types";

const stepKey = (turn: number, step: number): string => `${turn}:${step}`;

interface Notice {
  key: string;
  turn: number;
  tone: NoticeItem["tone"];
  text: string;
}

interface AssistantMessage {
  turn: number;
  step: number;
  content: string;
  interrupted: boolean;
  usage: Usage | null;
}

interface ToolResult {
  callId: string;
  result: ContentBlock[];
  error: string | null;
  ui: ToolUi | null;
}

export class TimelineDraft {
  private readonly items: TimelineItem[] = [];
  private readonly assistantAt = new Map<string, number>();
  private readonly toolAt = new Map<string, number>();
  private readonly closed = new Set<number>();
  private compactionAt: number | null = null;
  private lastTurn: number | null = null;

  rememberTurn(turn: number): void {
    this.lastTurn = turn;
  }

  onUserMessage(key: string, turn: number, content: string): void {
    this.items.push({
      kind: "user",
      key,
      turn,
      content,
      invoked: display(content),
    });
  }

  addNotice({ key, turn, tone, text }: Notice): void {
    this.items.push({ kind: "notice", key, turn, tone, text });
  }

  onAssistantText(turn: number, step: number, text: string): void {
    const key = stepKey(turn, step);
    const at = this.assistantAt.get(key);
    if (at === undefined) {
      this.assistantAt.set(key, this.items.length);
      this.items.push({
        kind: "assistant",
        key: `a${key}`,
        turn,
        step,
        content: text,
        streaming: true,
        interrupted: false,
        usage: null,
      });
      return;
    }
    const item = this.items[at];
    if (item?.kind !== "assistant") return;
    this.items[at] = { ...item, content: item.content + text };
  }

  onAssistantMessage({
    turn,
    step,
    content,
    interrupted,
    usage,
  }: AssistantMessage): void {
    const key = stepKey(turn, step);
    const at = this.assistantAt.get(key);
    const settled: TimelineItem = {
      kind: "assistant",
      key: `a${key}`,
      turn,
      step,
      content,
      streaming: false,
      interrupted,
      usage,
    };
    if (at === undefined) {
      this.assistantAt.set(key, this.items.length);
      this.items.push(settled);
      return;
    }
    this.items[at] = settled;
  }

  onToolCall(turn: number, step: number, call: ToolCall): void {
    this.toolAt.set(call.id, this.items.length);
    this.items.push({
      kind: "tool",
      key: `t${call.id}`,
      turn,
      step,
      call,
      result: null,
      error: null,
      ui: null,
    });
  }

  onToolResult({ callId, result, error, ui }: ToolResult): void {
    const at = this.toolAt.get(callId);
    if (at === undefined) return;
    const item = this.items[at];
    if (item?.kind !== "tool") return;
    this.items[at] = { ...item, result, error, ui };
  }

  onCompactionStart(
    key: string,
    turn: number | null,
    tokens: number | null,
  ): void {
    this.compactionAt = this.items.length;
    this.items.push({
      kind: "compaction",
      key,
      turn,
      tokens,
      summary: null,
      error: null,
      pending: true,
    });
  }

  onCompactionEnd(summary: string | null, error: string | null): void {
    const at = this.compactionAt;
    if (at === null) return;
    const item = this.items[at];
    if (item?.kind !== "compaction") return;
    this.items[at] = { ...item, summary, error, pending: false };
    this.compactionAt = null;
  }

  onTurnEnd(turn: number): void {
    this.closed.add(turn);
  }

  toTimeline(): Timeline {
    const opening = this.items.find((item) => item.kind === "user");
    return {
      items: this.items,
      openTurn:
        this.lastTurn !== null && !this.closed.has(this.lastTurn)
          ? this.lastTurn
          : null,
      openingMessage: opening ? opening.content : null,
    };
  }
}
