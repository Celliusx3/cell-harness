"use client";

import { FileIcon, FolderIcon, Trash2Icon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { sizeLabel } from "@/components/computer/files";
import { BUTTON, FilePreview, type OpenedFile } from "@/components/workspace/FilePreview";
import {
  childPath,
  deleteQuestion,
  deleteWorkspaceEntry,
  entryPath,
  listWorkspace,
  type WorkspaceEntry,
  type WorkspaceListing,
  watchWorkspace,
  workspaceCrumbs,
} from "@/components/workspace/workspace";
import { fileUrl } from "@/lib/api";

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : "The workspace could not be read.";
}

function stillListed(opened: OpenedFile | null, listing: WorkspaceListing): OpenedFile | null {
  const kept = opened !== null && listing.entries.some((entry) => entry.kind === "file" && entry.name === opened.name);
  return kept ? opened : null;
}

/** One chat's workspace: one folder at a time, or one file shown, each served by that chat. */
export function WorkspacePanel({ chatId }: { chatId: string }) {
  const [listing, setListing] = useState<WorkspaceListing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [opened, setOpened] = useState<OpenedFile | null>(null);
  const latestRequest = useRef(0);
  const shownPath = useRef<string | null>(null);

  const openFolder = useCallback(
    async (path: string) => {
      const request = ++latestRequest.current;
      setError(null);
      setOpened(null);
      try {
        const listed = await listWorkspace(chatId, path);
        if (request === latestRequest.current) setListing(listed);
      } catch (err: unknown) {
        if (request === latestRequest.current) setError(messageOf(err));
      }
    },
    [chatId],
  );

  const relist = useCallback(
    async (path: string) => {
      const request = ++latestRequest.current;
      try {
        const listed = await listWorkspace(chatId, path);
        if (request !== latestRequest.current) return;
        setListing(listed);
        setOpened((current) => stillListed(current, listed));
      } catch (err: unknown) {
        if (request === latestRequest.current) setError(messageOf(err));
      }
    },
    [chatId],
  );

  useEffect(() => {
    shownPath.current = listing?.path ?? null;
  }, [listing]);

  useEffect(() => {
    void openFolder("");
  }, [openFolder]);

  useEffect(
    () =>
      watchWorkspace(chatId, (folder) => {
        if (folder === shownPath.current) void relist(folder);
      }),
    [chatId, relist],
  );

  const deleteEntry = useCallback(
    async (folder: string, name: string) => {
      if (!window.confirm(deleteQuestion(name))) return;
      try {
        await deleteWorkspaceEntry(chatId, childPath(folder, name));
      } catch (err: unknown) {
        setError(messageOf(err));
        return;
      }
      await openFolder(folder);
    },
    [chatId, openFolder],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Crumbs path={listing?.path ?? ""} onOpen={(path) => void openFolder(path)} />
      {error !== null && (
        <p role="alert" className="bg-danger-soft px-3 py-2 break-words text-danger">
          {error}
        </p>
      )}
      {opened !== null ? (
        <FilePreview file={opened} onClose={() => setOpened(null)} />
      ) : (
        <div className="min-h-0 flex-1 overflow-auto">
          {listing !== null && (
            <Entries
              chatId={chatId}
              listing={listing}
              onOpen={(path) => void openFolder(path)}
              onOpenFile={setOpened}
              onDelete={(name) => void deleteEntry(listing.path, name)}
            />
          )}
        </div>
      )}
    </div>
  );
}

function Crumbs({ path, onOpen }: { path: string; onOpen: (path: string) => void }) {
  const trail = workspaceCrumbs(path);
  return (
    <nav aria-label="Path" className="flex min-h-10 flex-wrap items-center border-b border-line px-3 py-1.5 text-xs">
      {trail.map((crumb, at) =>
        at === trail.length - 1 ? (
          <span key={crumb.path} className="break-all text-ink">
            {at > 0 && "/"}
            {crumb.name}
          </span>
        ) : (
          <span key={crumb.path} className="break-all text-ink-soft">
            {at > 0 && "/"}
            <button type="button" onClick={() => onOpen(crumb.path)} className="hover:text-ink">
              {crumb.name}
            </button>
          </span>
        ),
      )}
    </nav>
  );
}

interface EntriesProps {
  chatId: string;
  listing: WorkspaceListing;
  onOpen: (path: string) => void;
  onOpenFile: (file: OpenedFile) => void;
  onDelete: (name: string) => void;
}

function Entries({ chatId, listing, onOpen, onOpenFile, onDelete }: EntriesProps) {
  if (listing.entries.length === 0) {
    return <p className="px-3 py-3 text-ink-soft">This folder is empty.</p>;
  }
  return (
    <ul>
      {listing.entries.map((entry) =>
        entry.kind === "folder" ? (
          <li key={entry.name} className="flex items-center gap-2 px-3 py-1.5 hover:bg-surface-sunken">
            <button
              type="button"
              onClick={() => onOpen(childPath(listing.path, entry.name))}
              className="flex min-w-0 flex-1 items-center gap-2 text-left"
            >
              <FolderIcon className="size-4 shrink-0 text-ink-soft" aria-hidden />
              <span className="min-w-0 break-all">{entry.name}</span>
            </button>
            <DeleteButton name={entry.name} onDelete={onDelete} />
          </li>
        ) : (
          <FileRow
            key={entry.name}
            entry={entry}
            url={fileUrl({ kind: "chat", id: chatId }, entryPath(listing, entry.name))}
            onOpen={onOpenFile}
            onDelete={onDelete}
          />
        ),
      )}
    </ul>
  );
}

interface FileRowProps {
  entry: WorkspaceEntry;
  url: string;
  onOpen: (file: OpenedFile) => void;
  onDelete: (name: string) => void;
}

function DeleteButton({ name, onDelete }: { name: string; onDelete: (name: string) => void }) {
  return (
    <button
      type="button"
      aria-label={`Delete ${name}`}
      onClick={() => onDelete(name)}
      className="shrink-0 rounded-md p-1 text-ink-soft transition hover:bg-danger-soft hover:text-danger"
    >
      <Trash2Icon className="size-4" aria-hidden />
    </button>
  );
}

function FileRow({ entry, url, onOpen, onDelete }: FileRowProps) {
  return (
    <li className="flex items-center gap-2 px-3 py-1.5 hover:bg-surface-sunken">
      <button
        type="button"
        onClick={() => onOpen({ name: entry.name, size: entry.size, url })}
        className="flex min-w-0 flex-1 items-center gap-2 text-left"
      >
        <FileIcon className="size-4 shrink-0 text-ink-soft" aria-hidden />
        <span className="min-w-0 break-all">{entry.name}</span>
        <span className="ml-auto shrink-0 text-xs text-ink-soft tabular-nums">{sizeLabel(entry.size)}</span>
      </button>
      <a href={url} download={entry.name} className={`shrink-0 ${BUTTON}`}>
        Download
      </a>
      <DeleteButton name={entry.name} onDelete={onDelete} />
    </li>
  );
}
