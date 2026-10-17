"use client";

import { ArrowUp, Paperclip, Square } from "lucide-react";
import { type DragEvent, useEffect, useRef, useState } from "react";

import { AttachmentChips } from "@/components/conversation/AttachmentChips";
import { useAttachments } from "@/components/conversation/useAttachments";
import type { ChatFile } from "@/lib/types";

/** Whether a drag carries files, rather than text the textarea should take. */
const carriesFiles = (transfer: DataTransfer) => transfer.types.includes("Files");

interface Props {
  /** The chat that attached files are uploaded into. */
  chatId: string;
  running: boolean;
  onSend(prompt: string, files: ChatFile[]): void;
  onStop(): void;
  autoFocus?: boolean;
  initialDraft?: string;
}

/** The composer, with the files attached to the next message, and the stop button while a turn runs. */
export function Composer({ chatId, running, onSend, onStop, autoFocus, initialDraft }: Props) {
  const [draft, setDraft] = useState(initialDraft ?? "");
  const [dragging, setDragging] = useState(false);
  const box = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  const attachments = useAttachments(chatId);

  useEffect(() => {
    if (!autoFocus || initialDraft === undefined) return;
    box.current?.setSelectionRange(initialDraft.length, initialDraft.length);
  }, [autoFocus, initialDraft]);

  const canSend = draft.trim() !== "" && !attachments.uploading;

  const submit = () => {
    const prompt = draft.trim();
    if (!prompt || attachments.uploading) return;
    onSend(prompt, attachments.uploaded);
    setDraft("");
    attachments.clear();
    box.current?.focus();
  };

  const dragOver = (event: DragEvent<HTMLDivElement>) => {
    if (!carriesFiles(event.dataTransfer)) return;
    event.preventDefault();
    setDragging(true);
  };

  const dragLeave = (event: DragEvent<HTMLDivElement>) => {
    const into = event.relatedTarget;
    if (into instanceof Node && event.currentTarget.contains(into)) return;
    setDragging(false);
  };

  const drop = (event: DragEvent<HTMLDivElement>) => {
    if (!carriesFiles(event.dataTransfer)) return;
    event.preventDefault();
    setDragging(false);
    attachments.add(Array.from(event.dataTransfer.files));
  };

  return (
    <div className="relative bg-surface px-4 pb-5 pt-2 before:pointer-events-none before:absolute before:inset-x-0 before:bottom-full before:h-8 before:bg-gradient-to-t before:from-surface before:to-transparent before:content-['']">
      <div
        onDragOver={dragOver}
        onDragLeave={dragLeave}
        onDrop={drop}
        className={`mx-auto flex max-w-3xl flex-col rounded-2xl border bg-surface-raised p-2 shadow-sm transition focus-within:border-accent ${
          dragging ? "border-accent bg-accent-soft" : "border-line"
        }`}
      >
        <AttachmentChips items={attachments.items} onRemove={attachments.remove} />
        <div className="flex items-end gap-2">
          <input
            ref={picker}
            type="file"
            multiple
            hidden
            onChange={(event) => {
              attachments.add(Array.from(event.target.files ?? []));
              event.target.value = "";
            }}
          />
          <button
            type="button"
            onClick={() => picker.current?.click()}
            aria-label="Attach files"
            title="Attach files"
            className="flex size-9 shrink-0 items-center justify-center rounded-xl text-ink-soft transition hover:bg-surface-sunken hover:text-ink"
          >
            <Paperclip size={16} />
          </button>
          <textarea
            ref={box}
            autoFocus={autoFocus}
            rows={1}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              // An IME committing a candidate fires Enter too; `isComposing` tells them apart.
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder={running ? "Reply — it will be answered next" : "Send a message"}
            className="max-h-48 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-ink-soft disabled:opacity-60"
          />
          {running && (
            <button
              onClick={onStop}
              aria-label="Stop"
              className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-danger text-white transition hover:opacity-90"
            >
              <Square size={14} fill="currentColor" />
            </button>
          )}
          <button
            onClick={submit}
            disabled={!canSend}
            aria-label="Send"
            title={attachments.uploading ? "Waiting for files to finish uploading" : undefined}
            className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent text-white transition hover:opacity-90 disabled:opacity-35"
          >
            <ArrowUp size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
