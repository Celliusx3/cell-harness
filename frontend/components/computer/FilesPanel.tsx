"use client";

import { FileIcon, FolderIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  baseName,
  crumbs,
  downloadBytes,
  type FileEntry,
  imageType,
  listFolder,
  readText,
  sizeLabel,
  uploadFiles,
} from "@/components/computer/files";

type Preview =
  | { kind: "text"; path: string; content: string }
  | { kind: "image"; path: string; url: string };

interface FilesPanelProps {
  canUpload: boolean;
}

const BUTTON =
  "rounded-md border border-line px-2 py-0.5 text-xs text-ink-soft transition hover:text-ink disabled:opacity-40";
const OCTET_STREAM = "application/octet-stream";

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : "The computer could not be reached.";
}

function save(path: string, bytes: Uint8Array<ArrayBuffer>): void {
  const url = URL.createObjectURL(new Blob([bytes], { type: imageType(path) ?? OCTET_STREAM }));
  const link = document.createElement("a");
  link.href = url;
  link.download = baseName(path);
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** The computer's home folder: browse, preview text and images, download, and upload. */
export function FilesPanel({ canUpload }: FilesPanelProps) {
  const [folder, setFolder] = useState("");
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const latestRequest = useRef(0);

  const openFolder = useCallback(async (path: string) => {
    const request = ++latestRequest.current;
    setError(null);
    try {
      const listed = await listFolder(path);
      if (request !== latestRequest.current) return;
      setFolder(path);
      setEntries(listed);
      setPreview(null);
    } catch (err: unknown) {
      if (request === latestRequest.current) setError(messageOf(err));
    }
  }, []);

  useEffect(() => {
    void openFolder("");
  }, [openFolder]);

  useEffect(() => {
    if (preview?.kind !== "image") return;
    const url = preview.url;
    return () => URL.revokeObjectURL(url);
  }, [preview]);

  async function show(entry: FileEntry) {
    if (entry.kind === "dir") return openFolder(entry.path);
    setError(null);
    try {
      const type = imageType(entry.path);
      if (type === undefined) {
        setPreview({ kind: "text", path: entry.path, content: await readText(entry.path) });
      } else {
        const blob = new Blob([await downloadBytes(entry.path)], { type });
        setPreview({ kind: "image", path: entry.path, url: URL.createObjectURL(blob) });
      }
    } catch (err: unknown) {
      setError(messageOf(err));
    }
  }

  async function download(path: string) {
    setError(null);
    try {
      save(path, await downloadBytes(path));
    } catch (err: unknown) {
      setError(messageOf(err));
    }
  }

  async function upload(files: File[]) {
    setBusy(true);
    setError(null);
    try {
      await uploadFiles(folder, files);
      await openFolder(folder);
    } catch (err: unknown) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  const trail = crumbs(preview?.path ?? folder);
  return (
    <section aria-label="Files" className="flex min-h-0 flex-1 flex-col text-sm">
      <div className="flex items-center gap-2 border-b border-line px-3 py-1.5">
        <nav aria-label="Path" className="flex min-w-0 flex-1 flex-wrap items-center text-xs">
          {trail.map((crumb, at) =>
            at === trail.length - 1 ? (
              <span key={crumb.path} className="break-all text-ink">
                {at > 0 && "/"}
                {crumb.name}
              </span>
            ) : (
              <span key={crumb.path} className="break-all text-ink-soft">
                {at > 0 && "/"}
                <button type="button" onClick={() => void openFolder(crumb.path)} className="hover:text-ink">
                  {crumb.name}
                </button>
              </span>
            ),
          )}
        </nav>
        {preview !== null ? (
          <>
            <button type="button" onClick={() => void download(preview.path)} className={BUTTON}>
              Download
            </button>
            <button type="button" onClick={() => setPreview(null)} className={BUTTON}>
              Close
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={() => picker.current?.click()}
              disabled={!canUpload || busy}
              title={canUpload ? "Add files from your machine to this folder" : "Take control first"}
              className={BUTTON}
            >
              {busy ? "Uploading…" : "Upload"}
            </button>
            <input
              ref={picker}
              type="file"
              multiple
              hidden
              onChange={(event) => {
                const chosen = Array.from(event.target.files ?? []);
                event.target.value = "";
                if (chosen.length > 0) void upload(chosen);
              }}
            />
          </>
        )}
      </div>

      {error !== null && (
        <p role="alert" className="bg-danger-soft px-3 py-2 break-words text-danger">
          {error}
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-auto">
        {preview === null ? (
          <ul>
            {entries.map((entry) => (
              <li key={entry.path} className="group flex items-center hover:bg-surface-sunken">
                <button
                  type="button"
                  onClick={() => void show(entry)}
                  className="flex min-w-0 flex-1 items-center gap-2 px-3 py-1.5 text-left"
                >
                  {entry.kind === "dir" ? (
                    <FolderIcon className="size-4 shrink-0 text-ink-soft" aria-hidden />
                  ) : (
                    <FileIcon className="size-4 shrink-0 text-ink-soft" aria-hidden />
                  )}
                  <span className="min-w-0 break-all">{baseName(entry.path)}</span>
                  {entry.kind === "file" && (
                    <span className="ml-auto shrink-0 text-xs text-ink-soft tabular-nums">
                      {sizeLabel(entry.size)}
                    </span>
                  )}
                </button>
                {entry.kind === "file" && (
                  <button
                    type="button"
                    onClick={() => void download(entry.path)}
                    className={`mr-2 ${BUTTON}`}
                  >
                    Download
                  </button>
                )}
              </li>
            ))}
          </ul>
        ) : preview.kind === "text" ? (
          <pre className="p-3 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap">
            {preview.content}
          </pre>
        ) : (
          <img src={preview.url} alt={baseName(preview.path)} className="mx-auto max-h-full max-w-full p-3" />
        )}
      </div>
    </section>
  );
}
