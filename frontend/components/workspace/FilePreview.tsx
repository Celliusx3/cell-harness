"use client";

import { XIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { imageType, sizeLabel } from "@/components/computer/files";
import { TEXT_PREVIEW_BYTES, textOf } from "@/components/workspace/preview";
import { readHead } from "@/components/workspace/workspace";

export const BUTTON =
  "rounded-md border border-line px-2 py-0.5 text-xs text-ink-soft transition hover:text-ink";

export interface OpenedFile {
  name: string;
  size: number;
  url: string;
}

type Shown =
  | { kind: "loading" }
  | { kind: "text"; text: string; cut: boolean }
  | { kind: "other" }
  | { kind: "failed"; message: string };

async function shownOf(url: string): Promise<Shown> {
  try {
    const head = await readHead(url, TEXT_PREVIEW_BYTES);
    const text = textOf(head);
    return text === null ? { kind: "other" } : { kind: "text", text, cut: head.cut };
  } catch (err: unknown) {
    return { kind: "failed", message: err instanceof Error ? err.message : "The file could not be read." };
  }
}

/** One file of the workspace shown in the panel: an image, the head of a text file, or its name and size. */
export function FilePreview({ file, onClose }: { file: OpenedFile; onClose: () => void }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex items-center gap-2 border-b border-line px-3 py-1.5">
        <span className="min-w-0 break-all">{file.name}</span>
        <span className="ml-auto shrink-0 text-xs text-ink-soft tabular-nums">{sizeLabel(file.size)}</span>
        <a href={file.url} download={file.name} className={`shrink-0 ${BUTTON}`}>
          Download
        </a>
        <button type="button" onClick={onClose} aria-label="Back to the folder" className="shrink-0 text-ink-soft hover:text-ink">
          <XIcon className="size-4" aria-hidden />
        </button>
      </header>
      <div className="min-h-0 flex-1 overflow-auto">
        {imageType(file.name) === undefined ? (
          <FetchedBody key={file.url} file={file} />
        ) : (
          <img src={file.url} alt={file.name} className="max-w-full p-3" />
        )}
      </div>
    </div>
  );
}

function FetchedBody({ file }: { file: OpenedFile }) {
  const [shown, setShown] = useState<Shown>({ kind: "loading" });

  useEffect(() => {
    let current = true;
    void shownOf(file.url).then((next) => {
      if (current) setShown(next);
    });
    return () => {
      current = false;
    };
  }, [file.url]);

  switch (shown.kind) {
    case "loading":
      return <p className="px-3 py-3 text-ink-soft">Loading…</p>;
    case "failed":
      return (
        <p role="alert" className="bg-danger-soft px-3 py-2 break-words text-danger">
          {shown.message}
        </p>
      );
    case "other":
      return <p className="px-3 py-3 text-ink-soft">This file cannot be shown here. Download it to open it.</p>;
    case "text":
      return (
        <>
          {shown.cut && <p className="px-3 pt-2 text-xs text-ink-soft">Showing the first 256 KB</p>}
          <pre className="px-3 py-2 font-mono text-xs whitespace-pre-wrap break-words">{shown.text}</pre>
        </>
      );
    default: {
      const _exhaustive: never = shown;
      return _exhaustive;
    }
  }
}
