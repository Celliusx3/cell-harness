import type {
  AppResource,
  AppToolResult,
  Approvals,
  BundledFile,
  ConversationDetail,
  ConversationSummary,
  ClientOutput,
  Decision,
  MessageAccepted,
  SkillFile,
  SkillList,
  SkillSummary,
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

/** A `FormData` body is left unlabelled so the browser can write its own multipart boundary. */
function headersFor(body: BodyInit | null | undefined) {
  return typeof body === "string" ? { "content-type": "application/json" } : undefined;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: headersFor(init?.body),
  });
  if (!response.ok) {
    throw new ApiError(response.status, await detailOf(response));
  }
  return response.status === 204
    ? (undefined as T)
    : ((await response.json()) as T);
}

/** The backend's message, or a fallback. */
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
  }
  return `request failed (${response.status})`;
}

export const listConversations = () =>
  request<ConversationSummary[]>("/conversations");

export const getConversation = (id: string) =>
  request<ConversationDetail>(`/conversations/${id}`);

/** Create a conversation *and* send its first message */
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

/** Compact the conversation now. */
export const compactConversation = (id: string) =>
  request<void>(`/conversations/${id}/compact`, { method: "POST" });

/** The output of a client tool the browser saw called on the stream, or the person's decision on a gated call */
export const sendToolOutput = <T>(
  id: string,
  callId: string,
  output: ClientOutput<T> | Decision,
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

/** One file the skill bundles, read by its relative path. */
export const getSkillFile = (name: string, path: string) =>
  request<BundledFile>(
    `/skills/${name}/files/${path.split("/").map(encodeURIComponent).join("/")}`,
  );

/** Whole-file save into the editable root; the backend validates and refuses. */
export const putSkill = (name: string, text: string) =>
  request<void>(`/skills/${name}`, {
    method: "PUT",
    body: JSON.stringify({ text }),
  });

export const deleteSkill = (name: string) =>
  request<void>(`/skills/${name}`, { method: "DELETE" });

/** Unpack a zipped skill folder into the editable root, replacing a directory of the same name. */
export const uploadSkill = (file: File) => {
  const body = new FormData();
  body.append("file", file);
  return request<SkillSummary>("/skills", { method: "POST", body });
};

/** Every tool allowed always */
export const listApprovals = () => request<Approvals>("/approvals");

/** Make the tool ask again. */
export const revokeApproval = (tool: string) =>
  request<void>(`/approvals/${encodeURIComponent(tool)}`, { method: "DELETE" });

/** An MCP App's HTML, read from its server through the harness. */
export const getAppResource = (server: string, uri: string) =>
  request<AppResource>(
    `/mcp/${server}/resources?uri=${encodeURIComponent(uri)}`,
  );

/** A call the app makes back to its own server, proxied by the harness. */
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
