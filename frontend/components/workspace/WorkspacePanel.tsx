"use client";

import { FileIcon, FolderIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { sizeLabel } from "@/components/computer/files";
import {
  childPath,
  entryPath,
  listWorkspace,
  type WorkspaceEntry,
  type WorkspaceListing,
  workspaceCrumbs,
} from "@/components/workspace/workspace";
import { fileUrl } from "@/lib/api";

const BUTTON =
  "rounded-md border border-line px-2 py-0.5 text-xs text-ink-soft transition hover:text-ink";

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : "The workspace could not be read.";
}

/** The chat's workspace beside the chat: one folder at a time, each file downloadable. */
export function WorkspacePanel({ chatId }: { chatId: string }) {
  const [listing, setListing] = useState<WorkspaceListing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const latestRequest = useRef(0);

  const openFolder = useCallback(
    async (path: string) => {
      const request = ++latestRequest.current;
      setError(null);
      try {
        const listed = await listWorkspace(chatId, path);
        if (request === latestRequest.current) setListing(listed);
      } catch (err: unknown) {
        if (request === latestRequest.current) setError(messageOf(err));
      }
    },
    [chatId],
  );

  useEffect(() => {
    void openFolder("");
  }, [openFolder]);

  return (
    <section
      aria-label="Workspace files"
      className="hidden min-h-0 w-[26rem] shrink-0 flex-col border-l border-line bg-surface-raised text-sm lg:flex"
    >
      <Crumbs path={listing?.path ?? ""} onOpen={(path) => void openFolder(path)} />
      {error !== null && (
        <p role="alert" className="bg-danger-soft px-3 py-2 break-words text-danger">
          {error}
        </p>
      )}
      <div className="min-h-0 flex-1 overflow-auto">
        {listing !== null && (
          <Entries chatId={chatId} listing={listing} onOpen={(path) => void openFolder(path)} />
        )}
      </div>
    </section>
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
}

function Entries({ chatId, listing, onOpen }: EntriesProps) {
  if (listing.entries.length === 0) {
    return <p className="px-3 py-3 text-ink-soft">This folder is empty.</p>;
  }
  return (
    <ul>
      {listing.entries.map((entry) =>
        entry.kind === "folder" ? (
          <li key={entry.name} className="hover:bg-surface-sunken">
            <button
              type="button"
              onClick={() => onOpen(childPath(listing.path, entry.name))}
              className="flex w-full min-w-0 items-center gap-2 px-3 py-1.5 text-left"
            >
              <FolderIcon className="size-4 shrink-0 text-ink-soft" aria-hidden />
              <span className="min-w-0 break-all">{entry.name}</span>
            </button>
          </li>
        ) : (
          <FileRow key={entry.name} chatId={chatId} listing={listing} entry={entry} />
        ),
      )}
    </ul>
  );
}

function FileRow({ chatId, listing, entry }: { chatId: string; listing: WorkspaceListing; entry: WorkspaceEntry }) {
  return (
    <li className="flex items-center gap-2 px-3 py-1.5 hover:bg-surface-sunken">
      <FileIcon className="size-4 shrink-0 text-ink-soft" aria-hidden />
      <span className="min-w-0 break-all">{entry.name}</span>
      <span className="ml-auto shrink-0 text-xs text-ink-soft tabular-nums">{sizeLabel(entry.size)}</span>
      <a
        href={fileUrl({ kind: "chat", id: chatId }, entryPath(listing, entry.name))}
        download={entry.name}
        className={`shrink-0 ${BUTTON}`}
      >
        Download
      </a>
    </li>
  );
}
