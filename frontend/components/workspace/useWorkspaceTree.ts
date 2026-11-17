"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  EMPTY_TREE,
  seenFile,
  toggledFolder,
  type Tree,
  withListing,
  withoutPath,
} from "@/components/workspace/tree";
import { deleteWorkspaceEntry, listWorkspace, parentPath, watchWorkspace } from "@/components/workspace/workspace";

/** One chat's workspace tree as it is listed, and what the person can do to it. */
export interface WorkspaceTree {
  tree: Tree;
  workspace: string | null;
  isLive: boolean;
  error: string | null;
  toggleFolder(folder: string): void;
  markSeen(path: string): void;
  deleteEntry(path: string): Promise<boolean>;
}

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : "The workspace could not be read.";
}

/** The chat's workspace, its root listed at once, each open folder listed when it opens and again when it changes. */
export function useWorkspaceTree(chatId: string): WorkspaceTree {
  const [tree, setTree] = useState<Tree>(EMPTY_TREE);
  const [workspace, setWorkspace] = useState<string | null>(null);
  const [isLive, setLive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const shown = useRef<Tree>(EMPTY_TREE);
  const latest = useRef(new Map<string, number>());

  useEffect(() => {
    shown.current = tree;
  }, [tree]);

  const listFolder = useCallback(
    async (folder: string) => {
      const request = (latest.current.get(folder) ?? 0) + 1;
      latest.current.set(folder, request);
      try {
        const listing = await listWorkspace(chatId, folder);
        if (latest.current.get(folder) !== request) return;
        setWorkspace(listing.workspace);
        setTree((current) => withListing(current, folder, listing.entries));
        setError(null);
      } catch (err: unknown) {
        if (latest.current.get(folder) === request) setError(messageOf(err));
      }
    },
    [chatId],
  );

  useEffect(() => {
    void listFolder("");
  }, [listFolder]);

  useEffect(
    () =>
      watchWorkspace(chatId, {
        onChanged: (folder) => {
          if (shown.current.listings.has(folder)) void listFolder(folder);
        },
        onLive: setLive,
      }),
    [chatId, listFolder],
  );

  const toggleFolder = useCallback(
    (folder: string) => {
      if (!shown.current.expanded.has(folder)) void listFolder(folder);
      setTree((current) => toggledFolder(current, folder));
    },
    [listFolder],
  );

  const markSeen = useCallback((path: string) => setTree((current) => seenFile(current, path)), []);

  const deleteEntry = useCallback(
    async (path: string) => {
      try {
        await deleteWorkspaceEntry(chatId, path);
      } catch (err: unknown) {
        setError(messageOf(err));
        return false;
      }
      setTree((current) => withoutPath(current, path));
      await listFolder(parentPath(path));
      return true;
    },
    [chatId, listFolder],
  );

  return { tree, workspace, isLive, error, toggleFolder, markSeen, deleteEntry };
}
