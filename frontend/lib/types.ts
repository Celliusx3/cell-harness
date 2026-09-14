import type { CallToolResult } from "@modelcontextprotocol/client";

/**
 * The wire types, mirroring `backend/harness/session/models.py`.
 *
 * These are hand-written rather than generated, and that is a deliberate trade:
 * a generator would be a build step and a toolchain for nine small types. The
 * cost is that this file can fall behind, so a backend test asserts that every
 * `SessionEvent` discriminator appears here — see
 * `tests/unit/test_frontend_types.py`. Add an event type without a renderer and
 * the Python suite fails, not the browser.
 */

/** `assistant/chunk` payloads — the raw stream, kept for replay fidelity. */
export type StreamEvent =
  | { kind: "text"; text: string }
  | { kind: "tool_call"; call: ToolCall }
  | { kind: "completed"; full_text: string; tool_calls: ToolCall[]; usage: Usage | null }
  | { kind: "failed"; reason: string };

export interface ToolCall {
  id: string;
  name: string;
  /** The model's raw JSON string, unparsed — it may not even be valid JSON. */
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

/** Context the backend injected (the guardrail's note) — sent to the model in
 *  the user role, but not the person's words. */
export interface ApplicationMessage {
  role: "application";
  content: string;
}

export interface AssistantMessage {
  role: "assistant";
  content: string;
  tool_calls: ToolCall[];
}

/**
 * One part of a tool result — the Anthropic shape. `text` is prose;
 * `tool_reference` says the named tool is callable from the next request on.
 * Mirror of `Block` in `harness/llm/messages.py`; the Python test guards the
 * `type` literals.
 */
export type ContentBlock =
  | { type: "text"; text: string }
  | { type: "tool_reference"; tool_name: string };

export interface ToolMessage {
  role: "tool";
  tool_call_id: string;
  content: ContentBlock[];
}

/**
 * An MCP App bound to a tool result — mirror of `ToolUi` in
 * `harness/tools/definition.py`. `server` answers `resources/read` for
 * `resource_uri` and the app's own tool calls; `data` is the result's
 * `structuredContent`, which is what the app draws.
 */
export interface ToolUi {
  server: string;
  resource_uri: string;
  data: unknown;
}

/** `GET /api/mcp/{server}/resources` — an app's HTML and the policy to run it under. */
export interface AppResource {
  html: string;
  csp: string;
}

/**
 * `POST /api/mcp/{server}/tools/{name}` — the server's `CallToolResult`,
 * proxied verbatim. Typed by the MCP SDK because that is exactly what it is.
 */
export type AppToolResult = CallToolResult;

export type TurnEndReason = "completed" | "failed" | "cancelled";

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
      /** The typed failure code, or null on success. Not the rendered string. */
      error: string | null;
      /** The app that renders this result, when the tool declares one. */
      ui: ToolUi | null;
    };

export interface ConversationSummary {
  id: string;
  created_at: string;
  /** Empty until the opening turn's first flush stamps it. Needs a fallback. */
  title: string;
}

export interface MessageAccepted extends ConversationSummary {
  /**
   * True when the message was held behind a turn already running.
   *
   * It is *not in the log yet* — a queued message becomes a `user/message` only
   * when its turn starts — and this screen draws the conversation from the log.
   * So the client shows it itself until then; see `useConversation`.
   */
  queued: boolean;
}

export interface ConversationDetail extends ConversationSummary {
  events: SessionEvent[];
  next_cursor: number;
  running: boolean;
}
