import type { ConversationDetail, ConversationSummary } from "./types";

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
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
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
      return body.detail.map((item: { msg?: string }) => item.msg ?? "invalid").join("; ");
    }
  } catch {
    // A non-JSON error body is not worth a second failure mode.
  }
  return `request failed (${response.status})`;
}

export const listConversations = () => request<ConversationSummary[]>("/conversations");

export const getConversation = (id: string) =>
  request<ConversationDetail>(`/conversations/${id}`);

/** Create a conversation *and* send its first message — see the route's docstring. */
export const createConversation = (prompt: string) =>
  request<ConversationSummary>("/conversations", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });

export const sendMessage = (id: string, prompt: string) =>
  request<ConversationSummary>(`/conversations/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });

export const stopRun = (id: string) =>
  request<void>(`/conversations/${id}/run`, { method: "DELETE" });
