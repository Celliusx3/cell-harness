"use client";

import { FileIcon, LoaderCircle, TriangleAlert, X } from "lucide-react";

import type { Attachment } from "@/components/conversation/useAttachments";

/** The files on the composer: each one's name, how its upload went, and a way to take it off. */
export function AttachmentChips({
  items,
  onRemove,
}: {
  items: Attachment[];
  onRemove(key: number): void;
}) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5 px-1 pb-1">
      {items.map((item) => (
        <span
          key={item.key}
          title={item.kind === "failed" ? item.reason : item.name}
          className={`inline-flex max-w-full items-center gap-1.5 rounded-lg border px-2 py-1 text-xs ${
            item.kind === "failed"
              ? "border-danger/40 bg-danger-soft text-danger"
              : "border-line bg-surface text-ink"
          }`}
        >
          {item.kind === "uploading" ? (
            <LoaderCircle size={13} className="shrink-0 animate-spin text-ink-soft" />
          ) : item.kind === "failed" ? (
            <TriangleAlert size={13} className="shrink-0" />
          ) : (
            <FileIcon size={13} className="shrink-0 text-ink-soft" />
          )}
          <span className="break-all">{item.name}</span>
          {item.kind === "failed" && <span className="break-words">— {item.reason}</span>}
          <button
            type="button"
            onClick={() => onRemove(item.key)}
            aria-label={`Remove ${item.name}`}
            className="shrink-0 rounded text-ink-soft transition hover:text-ink"
          >
            <X size={13} />
          </button>
        </span>
      ))}
    </div>
  );
}
