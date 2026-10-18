"use client";

import { FileIcon } from "lucide-react";

import { fileUrl } from "@/lib/api";
import type { ChatFile } from "@/lib/types";

/** The types the backend serves inline, so a thumbnail can show them. */
const SHOWN_TYPES = new Set(["image/png", "image/jpeg", "image/webp", "image/gif"]);

const isShown = (file: ChatFile) => SHOWN_TYPES.has(file.media_type);

interface Props {
  /** The chat whose folder holds the files. */
  chatId: string;
  files: ChatFile[];
  align: "start" | "end";
}

/** Files in a message or a result: images as thumbnails that open full size, the rest as downloads. */
export function FileList({ chatId, files, align }: Props) {
  const images = files.filter(isShown);
  const others = files.filter((file) => !isShown(file));
  const justify = align === "end" ? "justify-end" : "justify-start";

  return (
    <div className="flex flex-col gap-2">
      {images.length > 0 && (
        <div className={`flex flex-wrap gap-2 ${justify}`}>
          {images.map((file) => (
            <a
              key={file.path}
              href={fileUrl(chatId, file.path)}
              target="_blank"
              rel="noopener noreferrer"
              title={file.name}
              className="block overflow-hidden rounded-lg border border-line bg-surface transition hover:opacity-90"
            >
              <img
                src={fileUrl(chatId, file.path)}
                alt={file.name}
                loading="lazy"
                className="size-24 object-cover"
              />
            </a>
          ))}
        </div>
      )}
      {others.length > 0 && (
        <div className={`flex flex-wrap gap-1.5 ${justify}`}>
          {others.map((file) => (
            <a
              key={file.path}
              href={fileUrl(chatId, file.path)}
              download={file.name}
              className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1 text-xs font-medium hover:bg-accent-soft"
            >
              <FileIcon size={13} className="shrink-0" />
              <span className="break-all">{file.name}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
