"use client";

import { useEffect, useState } from "react";

import { imageType, sizeLabel } from "@/components/computer/files";
import { TEXT_PREVIEW_BYTES, textOf } from "@/components/workspace/preview";
import { readHead } from "@/components/workspace/workspace";

export const DOWNLOAD_BUTTON =
  "flex h-[30px] shrink-0 items-center gap-1.5 rounded-lg border border-line px-3 font-medium text-ink transition hover:bg-surface-sunken";

/** A file the pane shows: its name, size, and where the file route serves it. */
export interface ShownFile {
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

/** A file's content, read again for each `version`: an image filling the view, the head of a text file with line numbers, or its name and size. */
export function FileBody({ file, version }: { file: ShownFile; version: number }) {
  const fresh = `${file.url}&v=${version}`;
  if (imageType(file.name) !== undefined) {
    return (
      <div className="min-h-0 flex-1 p-3">
        <img src={fresh} alt={file.name} className="size-full object-contain" />
      </div>
    );
  }
  return (
    <div className="min-h-0 flex-1 overflow-auto">
      <FetchedBody key={fresh} file={file} fresh={fresh} />
    </div>
  );
}

function FetchedBody({ file, fresh }: { file: ShownFile; fresh: string }) {
  const [shown, setShown] = useState<Shown>({ kind: "loading" });

  useEffect(() => {
    let current = true;
    void shownOf(fresh).then((next) => {
      if (current) setShown(next);
    });
    return () => {
      current = false;
    };
  }, [fresh]);

  switch (shown.kind) {
    case "loading":
      return <p className="px-5 py-3 text-ink-soft">Loading…</p>;
    case "failed":
      return (
        <p role="alert" className="bg-danger-soft px-5 py-2 break-words text-danger">
          {shown.message}
        </p>
      );
    case "other":
      return <OtherFile file={file} />;
    case "text":
      return <NumberedText text={shown.text} cut={shown.cut} />;
    default: {
      const _exhaustive: never = shown;
      return _exhaustive;
    }
  }
}

function OtherFile({ file }: { file: ShownFile }) {
  return (
    <div className="flex flex-col items-start gap-2 px-5 py-4">
      <p className="break-all font-medium">{file.name}</p>
      <p className="text-xs text-ink-soft tabular-nums">{sizeLabel(file.size)}</p>
      <p className="text-ink-soft">This file cannot be shown here. Download it to open it.</p>
      <a href={file.url} download={file.name} className={DOWNLOAD_BUTTON}>
        Download
      </a>
    </div>
  );
}

function NumberedText({ text, cut }: { text: string; cut: boolean }) {
  return (
    <>
      {cut && <p className="px-5 pt-2 text-xs text-ink-soft">Showing the first 256 KB</p>}
      <div className="grid grid-cols-[auto_minmax(0,1fr)] py-3.5 font-mono text-[13px] leading-[22px]">
        {text.split("\n").map((line, at) => (
          <Line key={at} number={at + 1} line={line} />
        ))}
      </div>
    </>
  );
}

function Line({ number, line }: { number: number; line: string }) {
  return (
    <>
      <span aria-hidden className="select-none pr-3 pl-4 text-right text-ink-soft/60 tabular-nums">
        {number}
      </span>
      <span className="whitespace-pre-wrap break-words pr-5 pl-5">{line}</span>
    </>
  );
}
