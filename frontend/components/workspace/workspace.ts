import { z } from "zod";

import { crumbs } from "@/components/computer/files";
import { type Head, headOf } from "@/components/workspace/preview";
import { request } from "@/lib/api";

const ROOT_NAME = "Workspace";

const WorkspaceEntry = z.object({
  name: z.string(),
  kind: z.enum(["file", "folder"]),
  size: z.number().int().nonnegative(),
});
export type WorkspaceEntry = z.infer<typeof WorkspaceEntry>;

const WorkspaceListing = z.object({
  path: z.string(),
  workspace: z.string(),
  entries: z.array(WorkspaceEntry),
});
export type WorkspaceListing = z.infer<typeof WorkspaceListing>;

/** One folder of the chat's workspace, by its path relative to the workspace, "" for the root. */
export async function listWorkspace(chatId: string, path: string): Promise<WorkspaceListing> {
  const query = new URLSearchParams({ path });
  return WorkspaceListing.parse(await request<unknown>(`/workspaces/${encodeURIComponent(chatId)}?${query}`));
}

/** The folder's path as crumbs back to the workspace's root. */
export function workspaceCrumbs(path: string) {
  return crumbs(path).map((crumb, at) => (at === 0 ? { ...crumb, name: ROOT_NAME } : crumb));
}

/** An entry's absolute path on disk, as the chat's file route takes it. */
export function entryPath(listing: WorkspaceListing, name: string): string {
  return [listing.workspace, listing.path, name].filter((part) => part !== "").join("/");
}

/** A relative folder path one level into `name`. */
export function childPath(folder: string, name: string): string {
  return folder === "" ? name : `${folder}/${name}`;
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
