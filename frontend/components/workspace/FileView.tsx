"use client";

import { DownloadIcon, Trash2Icon } from "lucide-react";
import { useEffect, useState } from "react";

import { sizeLabel } from "@/components/computer/files";
import { DeleteConfirm } from "@/components/workspace/DeleteConfirm";
import { DOWNLOAD_BUTTON, FileBody } from "@/components/workspace/FileBody";
import { timeAgo } from "@/components/workspace/relativeTime";
import type { WorkspaceEntry } from "@/components/workspace/workspace";

const TICK_MS = 30_000;

function useNow(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), TICK_MS);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}

interface FileViewProps {
  workspaceName: string;
  path: string;
  entry: WorkspaceEntry | undefined;
  url: string;
  onDelete: () => void;
}

/** One opened file: where it is, its size and change time, Download and Delete, then its content. */
export function FileView({ workspaceName, path, entry, url, onDelete }: FileViewProps) {
  const [isConfirming, setConfirming] = useState(false);
  const now = useNow();
  if (entry === undefined) {
    return <p className="flex-1 px-5 py-4 text-ink-soft">{path} is no longer in the workspace.</p>;
  }
  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="flex shrink-0 flex-col gap-2 border-b border-line px-3 py-1.5 pl-[18px]">
        <div className="flex min-h-8 items-center gap-2.5">
          <span className="min-w-0 flex-1 break-all text-xs text-ink-soft">
            {workspaceName} / {path} · {sizeLabel(entry.size)} · changed {timeAgo(entry.modified, now)}
          </span>
          <a href={url} download={entry.name} className={DOWNLOAD_BUTTON}>
            <DownloadIcon className="size-3.5" aria-hidden />
            Download
          </a>
          <button
            type="button"
            aria-label={`Delete ${entry.name}`}
            aria-expanded={isConfirming}
            onClick={() => setConfirming(true)}
            className="flex size-[30px] shrink-0 items-center justify-center rounded-lg border border-line text-ink-soft transition hover:bg-danger-soft hover:text-danger"
          >
            <Trash2Icon className="size-3.5" aria-hidden />
          </button>
        </div>
        {isConfirming && (
          <DeleteConfirm
            name={entry.name}
            onCancel={() => setConfirming(false)}
            onDelete={() => {
              setConfirming(false);
              onDelete();
            }}
          />
        )}
      </header>
      <FileBody file={{ name: entry.name, size: entry.size, url }} version={entry.modified.getTime()} />
    </div>
  );
}
