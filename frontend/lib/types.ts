import type { CallToolResult } from "@modelcontextprotocol/client";

/** The wire types, mirroring `backend/harness/session/models.py`. */

/** `assistant/chunk` payloads */
export type StreamEvent =
  | { kind: "text"; text: string }
  | { kind: "tool_call"; call: ToolCall }
  | {
      kind: "completed";
      full_text: string;
      tool_calls: ToolCall[];
      usage: Usage | null;
    }
  | { kind: "failed"; reason: string };

export interface ToolCall {
  id: string;
  name: string;
  /** The model's raw JSON string, unparsed */
  arguments: string;
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
}

export interface UserMessage {
  role: "user";
  content: string;
}

/** Context the backend injected (the guardrail's note) */
export interface ApplicationMessage {
  role: "application";
  content: string;
}

export interface AssistantMessage {
  role: "assistant";
  content: string;
  tool_calls: ToolCall[];
}

/** One part of a tool result */
export type ContentBlock =
  | { type: "text"; text: string }
  | { type: "tool_reference"; tool_name: string };

export interface ToolMessage {
  role: "tool";
  tool_call_id: string;
  content: ContentBlock[];
}

/** An MCP App bound to a tool result */
export interface ToolUi {
  server: string;
  resource_uri: string;
  data: unknown;
}

/** `GET /api/mcp/{server}/resources` */
export interface AppResource {
  html: string;
  csp: string;
}

/** `POST /api/mcp/{server}/tools/{name}` */
export type AppToolResult = CallToolResult;

export type TurnEndReason = "completed" | "failed" | "cancelled" | "pending";

/** Why a compaction ran */
export type CompactionTrigger = "auto" | "manual" | "overflow";

export type SessionEvent =
  | { type: "turn/start"; turn: number }
  | { type: "turn/end"; turn: number; reason: TurnEndReason }
  | { type: "user/message"; turn: number; message: UserMessage }
  | { type: "application/message"; turn: number; message: ApplicationMessage }
  | { type: "step/start"; turn: number; step: number }
  | { type: "step/end"; turn: number; step: number }
  | { type: "assistant/chunk"; turn: number; step: number; chunk: StreamEvent }
  | {
      type: "assistant/message";
      turn: number;
      step: number;
      message: AssistantMessage;
      usage: Usage | null;
      interrupted: boolean;
    }
  | { type: "tool/call"; turn: number; step: number; call: ToolCall }
  | {
      type: "tool/result";
      turn: number;
      step: number;
      message: ToolMessage;
      /** The typed failure code, or null on success. */
      error: string | null;
      /** The app that renders this result, when the tool declares one. */
      ui: ToolUi | null;
    }
  /** A summary is being attempted. */
  | { type: "compaction/start"; turn: number | null; trigger: CompactionTrigger; tokens: number | null }
  /** The attempt is over: `message` is what the model reads from here on, or `error` says why nothing changed. */
  | {
      type: "compaction/end";
      turn: number | null;
      message: ApplicationMessage | null;
      error: string | null;
    }
  /** These results are cleared from the model's view; the log and the screen keep them. */
  | { type: "compaction/prune"; turn: number | null; call_ids: string[] }
  | ApprovalGrantEvent;

/** The person allowed `tool` to run unasked for the rest of this conversation. */
export interface ApprovalGrantEvent {
  type: "approval/grant";
  turn: number;
  tool: string;
}

export interface ConversationSummary {
  id: string;
  created_at: string;
  /** Empty until the opening turn's first flush stamps it. */
  title: string;
}

export interface MessageAccepted extends ConversationSummary {
  /** True when the message was held behind a turn already running. */
  queued: boolean;
}

export interface ConversationDetail extends ConversationSummary {
  events: SessionEvent[];
  next_cursor: number;
  running: boolean;
}

export interface SkillSummary {
  name: string;
  description: string;
  dir: string;
  root: string;
  model_invocable: boolean;
  user_invocable: boolean;
  /** In `skills.editable`, so the page may save over it or delete it. */
  editable: boolean;
}

export interface SkillIssue {
  path: string;
  problem: string;
}

export interface SkillList {
  skills: SkillSummary[];
  problems: SkillIssue[];
}

export interface SkillFile {
  name: string;
  text: string;
  editable: boolean;
  files: string[];
}

/** `GET /api/skills/{name}/files/{path}` */
export interface BundledFile {
  path: string;
  text: string;
}

/** What the browser answers a client tool with */
export type ClientOutput<T> =
  | { kind: "shared"; data: T }
  | { kind: "declined" }
  | { kind: "unavailable"; reason: string };

/** `get_location`'s datum. */
export interface Location {
  latitude: number;
  longitude: number;
  accuracy_m: number;
}

/** How long an approval holds */
export type Scope = "once" | "conversation" | "always";

/** What the browser answers an approval gate with */
export type Decision = { kind: "approved"; scope: Scope } | { kind: "denied" };

/** `GET /api/approvals` */
export interface Approvals {
  tools: string[];
}
