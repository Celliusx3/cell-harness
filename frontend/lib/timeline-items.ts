/** The shapes `buildTimeline` produces */

import type { Invocation } from "@/lib/invocation";
import type { ContentBlock, ToolCall, ToolUi, Usage } from "@/lib/types";

export interface UserItem {
  kind: "user";
  key: string;
  turn: number;
  /** The whole message as logged and sent */
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
  /** The result's blocks */
  result: ContentBlock[] | null;
  /** The typed failure code, or null. */
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

export interface CompactionItem {
  kind: "compaction";
  key: string;
  turn: number | null;
  /** The context size that triggered it, when the log recorded one. */
  tokens: number | null;
  /** The summary the model now reads */
  summary: string | null;
  /** Why nothing changed, when it did not. */
  error: string | null;
  /** No `compaction/end` yet: the summary is being written. */
  pending: boolean;
}

export type TimelineItem =
  | UserItem
  | AssistantItem
  | ToolItem
  | NoticeItem
  | CompactionItem;

export interface Timeline {
  items: TimelineItem[];
  /** True while the last turn is still open */
  openTurn: number | null;
  /** The opening message, for a header whose stored title is not there yet. */
  openingMessage: string | null;
}

