import { z } from "zod";

import { type Head, headOf } from "@/components/workspace/preview";
import { request } from "@/lib/api";

const WorkspaceEntry = z.object({
  name: z.string(),
  kind: z.enum(["file", "folder"]),
  size: z.number().int().nonnegative(),
  modified: z.iso.datetime({ offset: true }).transform((text) => new Date(text)),
});
export type WorkspaceEntry = z.infer<typeof WorkspaceEntry>;

const WorkspaceListing = z.object({
  path: z.string(),
  workspace: z.string(),
  entries: z.array(WorkspaceEntry),
});
export type WorkspaceListing = z.infer<typeof WorkspaceListing>;

const WorkspaceChanged = z.object({ type: z.literal("workspace/changed"), folder: z.string() });

/** What a watcher of a chat's workspace is told. */
export interface WorkspaceWatcher {
  onChanged(folder: string): void;
  onLive(isLive: boolean): void;
}

/** Tells `watcher` each folder of the chat's workspace that changes, and whether it is watched, until closed. */
export function watchWorkspace(chatId: string, watcher: WorkspaceWatcher): () => void {
  const source = new EventSource(`/api/workspaces/${encodeURIComponent(chatId)}/changes`);
  source.addEventListener("workspace/watching", () => watcher.onLive(true));
  source.addEventListener("workspace/changed", (message: MessageEvent<string>) => {
    const changed = WorkspaceChanged.safeParse(JSON.parse(message.data));
    if (changed.success) watcher.onChanged(changed.data.folder);
  });
  source.addEventListener("error", () => watcher.onLive(false));
  return () => source.close();
}

/** One folder of the chat's workspace, by its path relative to the workspace, "" for the root. */
export async function listWorkspace(chatId: string, path: string): Promise<WorkspaceListing> {
  const query = new URLSearchParams({ path });
  return WorkspaceListing.parse(await request<unknown>(`/workspaces/${encodeURIComponent(chatId)}?${query}`));
}

/** Delete the file or folder at `path`, relative to the chat's workspace. */
export async function deleteWorkspaceEntry(chatId: string, path: string): Promise<void> {
  const query = new URLSearchParams({ path });
  await request<void>(`/workspaces/${encodeURIComponent(chatId)}?${query}`, { method: "DELETE" });
}

/** The question asked before `name` is deleted. */
export function deleteQuestion(name: string): string {
  return `Delete ${name}? Bots lose it too, and past messages that link it will not open it.`;
}

/** A relative path's absolute path on disk, as the chat's file route takes it. */
export function absolutePath(workspace: string, path: string): string {
  return path === "" ? workspace : `${workspace}/${path}`;
}

/** A relative path one level into `name`. */
export function childPath(folder: string, name: string): string {
  return folder === "" ? name : `${folder}/${name}`;
}

/** The relative folder holding `path`, "" for the root. */
export function parentPath(path: string): string {
  const cut = path.lastIndexOf("/");
  return cut === -1 ? "" : path.slice(0, cut);
}

/** Whether `path` is `folder` itself or lies inside it. */
export function isWithin(path: string, folder: string): boolean {
  return path === folder || path.startsWith(`${folder}/`);
}

/** The first `limit` bytes the file route serves at `url`; the rest is never read. */
export async function readHead(url: string, limit: number): Promise<Head> {
  const response = await fetch(url);
  if (!response.ok || response.body === null) {
    throw new Error(`The file could not be read (${response.status}).`);
  }
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (total <= limit) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    total += value.length;
  }
  await reader.cancel();
  return headOf(chunks, limit);
}
