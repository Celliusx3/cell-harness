import type {
  AppResource,
  AppToolResult,
  ConversationDetail,
  ConversationSummary,
  ClientOutput,
  MessageAccepted,
  SkillFile,
  SkillList,
} from "./types";

/** Thrown for any non-2xx, carrying the backend's `detail` so the UI can show it. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: init?.body ? { "content-type": "application/json" } : undefined,
  });
  if (!response.ok) {
    throw new ApiError(response.status, await detailOf(response));
  }
  return response.status === 204
    ? (undefined as T)
    : ((await response.json()) as T);
}

/**
 * The backend's message, or a fallback.
 *
 * FastAPI puts a string in `detail` for our `HTTPException`s and an array of
 * per-field objects for a 422 — hence the two shapes. Neither is truncated: a
 * corrupt-log 500 names the file and line, which is the whole point of passing
 * it through.
 */
async function detailOf(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) {
      return body.detail
        .map((item: { msg?: string }) => item.msg ?? "invalid")
        .join("; ");
    }
  } catch {
    // A non-JSON error body is not worth a second failure mode.
  }
  return `request failed (${response.status})`;
}

export const listConversations = () =>
  request<ConversationSummary[]>("/conversations");

export const getConversation = (id: string) =>
  request<ConversationDetail>(`/conversations/${id}`);

/** Create a conversation *and* send its first message — see the route's docstring. */
export const createConversation = (prompt: string) =>
  request<ConversationSummary>("/conversations", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });

export const sendMessage = (id: string, prompt: string) =>
  request<MessageAccepted>(`/conversations/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });

export const stopRun = (id: string) =>
  request<void>(`/conversations/${id}/run`, { method: "DELETE" });

/** Compact the conversation now. A 409 (running, or nothing to compact) is an
 *  `ApiError` the caller can surface. */
export const compactConversation = (id: string) =>
  request<void>(`/conversations/${id}/compact`, { method: "POST" });

/**
 * The output of a client tool the browser saw called on the stream — Vercel's
 * `addToolOutput`. 404 when that call is not the one waiting (answered,
 * expired, stopped), 409 when another tab beat this one — both mean "nothing
 * to do", and the stream carries the result. 422 is a bug in the handler.
 */
export const sendToolOutput = <T>(
  id: string,
  callId: string,
  output: ClientOutput<T>,
) =>
  request<void>(
    `/conversations/${id}/calls/${encodeURIComponent(callId)}/output`,
    {
      method: "POST",
      body: JSON.stringify(output),
    },
  );

export const listSkills = () => request<SkillList>("/skills");

export const getSkill = (name: string) => request<SkillFile>(`/skills/${name}`);

/** Whole-file save into the editable root; the backend validates and refuses. */
export const putSkill = (name: string, text: string) =>
  request<void>(`/skills/${name}`, {
    method: "PUT",
    body: JSON.stringify({ text }),
  });

export const deleteSkill = (name: string) =>
  request<void>(`/skills/${name}`, { method: "DELETE" });

/** An MCP App's HTML, read from its server through the harness. */
export const getAppResource = (server: string, uri: string) =>
  request<AppResource>(
    `/mcp/${server}/resources?uri=${encodeURIComponent(uri)}`,
  );

/**
 * A call the app makes back to its own server, proxied by the harness.
 * `resourceUri` says which app is asking — a tool bound to another app is refused.
 */
export const callAppTool = (
  server: string,
  name: string,
  args: Record<string, unknown>,
  resourceUri: string,
) =>
  request<AppToolResult>(`/mcp/${server}/tools/${encodeURIComponent(name)}`, {
    method: "POST",
    body: JSON.stringify({ arguments: args, resource_uri: resourceUri }),
  });
