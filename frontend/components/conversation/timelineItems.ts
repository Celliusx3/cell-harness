/** The shapes `buildTimeline` produces */

import type { Invocation } from "@/components/conversation/invocation";
import type { TicketAsk } from "@/lib/tickets";
import type {
  ApprovalMode,
  ContentBlock,
  ChatFile,
  SessionEvent,
  ToolCall,
  ToolUi,
  Usage,
} from "@/lib/types";

export interface UserItem {
  kind: "user";
  key: string;
  turn: number;
  /** The whole message as logged and sent */
  content: string;
  /** Set when the message is a `/name` expansion: the short form to show. */
  invoked: Invocation | null;
  /** What the person attached */
  files: ChatFile[];
}

export type Reminder = Extract<SessionEvent, { type: "schedule/reminder" }>["reminders"][number];

/** A turn a schedule opened: its reminders, in the order they fired. */
export interface ScheduledItem {
  kind: "scheduled";
  key: string;
  turn: number;
  reminders: Reminder[];
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
  /** The files the tool handed back, arriving with `tool/result`. */
  files: ChatFile[];
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

interface InstructionsItem {
  kind: "instructions";
  key: string;
}

/** The person switched the chat's mode here. */
interface ModeItem {
  kind: "mode";
  key: string;
  mode: ApprovalMode;
}

export type ScheduleChange = Extract<SessionEvent, { type: "schedule/change" }>["change"];

/** A schedule of this chat's bot was changed from Settings here. */
export interface ScheduleChangeItem {
  kind: "scheduleChange";
  key: string;
  change: ScheduleChange;
}

/** A worker's question in its ticket's report; `latest` when no later report of it follows. */
export interface TicketQuestionItem {
  kind: "ticketQuestion";
  key: string;
  turn: number;
  ticketId: string;
  question: string;
  ask: TicketAsk;
  options: string[];
  secretName: string | null;
  latest: boolean;
}

export type TimelineItem =
  | UserItem
  | ScheduledItem
  | AssistantItem
  | ToolItem
  | NoticeItem
  | CompactionItem
  | InstructionsItem
  | ModeItem
  | ScheduleChangeItem
  | TicketQuestionItem;

export interface Timeline {
  items: TimelineItem[];
  /** True while the last turn is still open */
  openTurn: number | null;
  /** In a group's chat, the bot that spoke each turn. */
  speakers: ReadonlyMap<number, Speaker>;
}

export interface Speaker {
  id: string;
  name: string;
}

