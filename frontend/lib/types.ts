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

/** An image the model is shown, kept once under the hash of its bytes. */
export interface ImageBlock {
  type: "image";
  media_type: string;
  sha256: string;
}

/** One part of a tool result */
export type ContentBlock =
  | { type: "text"; text: string }
  | { type: "tool_reference"; tool_name: string }
  | ImageBlock;

export interface ToolMessage {
  role: "tool";
  tool_call_id: string;
  content: ContentBlock[];
}

/** A file in a chat's folder: where it is on disk, its name, type and size. */
export interface ChatFile {
  path: string;
  name: string;
  media_type: string;
  size: number;
}

/** An MCP App bound to a tool result */
export interface ToolUi {
  server: string;
  resource_uri: string;
  data: unknown;
}

/** `GET /api/mcp`: every server the harness is set up with, by its tool namespace. */
export interface ServerList {
  servers: string[];
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
  /** `bot_id` is the bot speaking this turn; null in older logs. */
  | { type: "turn/start"; turn: number; bot_id?: string | null }
  | { type: "turn/end"; turn: number; reason: TurnEndReason }
  /** `files` are what the person attached, each in the chat's folder. */
  | { type: "user/message"; turn: number; message: UserMessage; files: ChatFile[] }
  | {
      type: "bot/message";
      turn: number;
      message: {
        from_bot_id: string;
        from_name: string;
        text: string;
        hop: number;
        intent: "request" | "result";
      };
    }
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
      /** The files the tool handed back, each in the chat's folder. */
      files: ChatFile[];
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
  | ApprovalGrantEvent
  /** A bot answering from here on, and the instructions its turns are prompted with. */
  | { type: "bot/instructions"; name: string; instructions: string; bot_id?: string | null }
  /** The group this chat belongs to, and its members' names. */
  | { type: "group/members"; name: string; members: string[] }
  | { type: "chat/cleared" };

/** The person allowed `tool` to run unasked for the rest of this conversation. */
export interface ApprovalGrantEvent {
  type: "approval/grant";
  turn: number;
  tool: string;
}

export interface Bot {
  id: string;
  name: string;
  instructions: string;
  secret_names: string[];
}

export type BotDraft = Pick<Bot, "name" | "instructions">;

/** Two to six bots sharing one chat, whose id is the group's; they take turns in member order. */
export interface Group {
  id: string;
  name: string;
  member_ids: string[];
}

export type GroupDraft = Pick<Group, "name" | "member_ids">;

/** `GET /api/secrets`: one saved key, its site, and the bots allowed to use it; never its value. */
export interface SecretSummary {
  name: string;
  origin: string;
  auth: "bearer" | "header";
  header_name: string | null;
  bots: { id: string; name: string }[];
}

export interface MessageAccepted {
  id: string;
  created_at: string;
  /** True when the message was held behind a turn already running. */
  queued: boolean;
}

export interface ConversationDetail {
  id: string;
  created_at: string;
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
export type ClientAnswer<T> =
  | { kind: "shared"; data: T }
  | { kind: "declined" }
  | { kind: "unavailable"; reason: string };

/** `get_location`'s datum. */
export interface Location {
  latitude: number;
  longitude: number;
  accuracy_m: number;
}

/** `ask_user`'s datum. */
export interface Answer {
  choice: string;
}

/** What `hand_over` is called with: the one step the person has to do. */
export interface HandOver {
  step: string;
}

/** `hand_over`'s datum: true for I'm done, false for Skip. */
export interface HandOverAnswer {
  finished: boolean;
}

/** How long an approval holds */
export type Scope = "once" | "conversation" | "always";

/** What the browser answers an approval gate with */
export type Decision = { kind: "approved"; scope: Scope } | { kind: "denied" };

/** `GET /api/approvals` */
export interface Approvals {
  tools: string[];
}

/** `GET /api/credentials`: one key the harness itself holds, never its value. */
export interface Credential {
  path: string;
  description: string;
  is_set: boolean;
  is_required: boolean;
  last_four: string | null;
  env_variable: string | null;
}

/** `GET /api/credentials`, with the harness's own address. */
export interface CredentialList {
  credentials: Credential[];
  direct_url: string;
  answering_pid: number;
}

/** `PUT /api/credentials`: a new key by path, or null to remove it. */
export type CredentialValues = Record<string, string | null>;
