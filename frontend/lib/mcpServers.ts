import { z } from "zod";

import { ApiError, detailOf, request } from "./api";
import type { ServerStatus } from "./types";

/** `GET /api/mcp/servers`: one server, how it runs, its plain settings, the keys it needs, and its state. */
export interface McpServer {
  id: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  needs: string[];
  built_in: boolean;
  status: ServerStatus;
  error: string;
}

/** `GET /api/mcp/servers`: the built-in servers first, then the person's own as added. */
export interface McpServerList {
  servers: McpServer[];
}

/** `PUT /api/mcp/servers/{id}`: how to run a server, its plain settings, and the names of the keys it needs. */
export interface McpServerChange {
  command: string;
  args: string[];
  env: Record<string, string>;
  needs: string[];
}

/** `POST /api/mcp/servers`: a change under the name its tools are called by. */
export interface McpServerDraft extends McpServerChange {
  id: string;
}

const RefusedField = z.object({ loc: z.array(z.union([z.string(), z.number()])), msg: z.string() });
const RefusedFields = z.object({ detail: z.array(RefusedField) });

/** One field the harness refused in a 422, where it sits in the request and why. */
export type RefusedField = z.infer<typeof RefusedField>;

/** A 422: the harness refused these fields of the request. */
export class FieldsRefused extends ApiError {
  constructor(readonly fields: RefusedField[]) {
    super(422, fields.map((field) => field.msg).join("; "));
  }
}

/** Every server the harness is set up with, read through the page's own server. */
export const listMcpServers = () => request<McpServerList>("/mcp/servers");

/** Whether this browser reaches the harness directly, which only a page on its own Mac does. */
export async function canChangeServers(directUrl: string): Promise<boolean> {
  try {
    return (await fetch(`${directUrl}/api/mcp/servers`)).ok;
  } catch {
    return false;
  }
}

export const addMcpServer = (directUrl: string, draft: McpServerDraft) =>
  sendToHarness(directUrl, "", { method: "POST", body: JSON.stringify(draft) });

export const changeMcpServer = (directUrl: string, id: string, change: McpServerChange) =>
  sendToHarness(directUrl, `/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(change) });

/** The server stops and its tools leave the bots; its capability keys stay on Credentials. */
export const removeMcpServer = (directUrl: string, id: string) =>
  sendToHarness(directUrl, `/${encodeURIComponent(id)}`, { method: "DELETE" });

export const restartMcpServer = (directUrl: string, id: string) =>
  sendToHarness(directUrl, `/${encodeURIComponent(id)}/restart`, { method: "POST" });

/** Whether a server is still starting, so the list is worth asking for again. */
export function isAnyStarting(servers: McpServer[]): boolean {
  return servers.some((server) => server.status === "connecting");
}

/** A server's state in words: "Running", "Waiting for a key: EXA_API_KEY", "Failed: <error>". */
export function stateLabel(server: McpServer): string {
  switch (server.status) {
    case "connected":
      return "Running";
    case "connecting":
      return "Starting";
    case "waiting":
      return server.needs.length === 0 ? "Waiting for a key" : `Waiting for a key: ${server.needs.join(", ")}`;
    case "failed":
      return server.error === "" ? "Failed" : `Failed: ${server.error}`;
    case "disconnected":
      return "Stopped";
    default: {
      const _exhaustive: never = server.status;
      return _exhaustive;
    }
  }
}

/** "npx -y exa-mcp-server": the command and its arguments as one line. */
export function commandLine(server: Pick<McpServer, "command" | "args">): string {
  return [server.command, ...server.args].join(" ");
}

/** Resolves when the harness at `directUrl` accepts; `FieldsRefused` for a 422, else `ApiError` with its detail. */
async function sendToHarness(directUrl: string, path: string, init: { method: string; body?: string }): Promise<void> {
  const response = await fetch(`${directUrl}/api/mcp/servers${path}`, {
    ...init,
    headers: init.body === undefined ? undefined : { "content-type": "application/json" },
  });
  if (response.ok) return;
  if (response.status === 422) {
    const refused = RefusedFields.safeParse(await response.clone().json().catch(() => null));
    if (refused.success) throw new FieldsRefused(refused.data.detail);
  }
  throw new ApiError(response.status, await detailOf(response));
}
