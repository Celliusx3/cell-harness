"use client";

import { useCallback, useMemo, useRef, useState } from "react";

import { ApiError, uploadFile } from "@/lib/api";
import type { ChatFile } from "@/lib/types";

/** One file the person is attaching: on its way up, saved in the chat's folder, or refused. */
export type Attachment =
  | { kind: "uploading"; key: number; name: string }
  | { kind: "uploaded"; key: number; name: string; stored: ChatFile }
  | { kind: "failed"; key: number; name: string; reason: string };

export interface Attachments {
  items: Attachment[];
  /** True while any file is still on its way up. */
  uploading: boolean;
  /** The files a message sent now would carry. */
  uploaded: ChatFile[];
  add(files: File[]): void;
  remove(key: number): void;
  clear(): void;
}

/** One upload, settled into what its chip shows. */
async function uploadAttachment(chatId: string, file: File, key: number): Promise<Attachment> {
  try {
    return { kind: "uploaded", key, name: file.name, stored: await uploadFile(chatId, file) };
  } catch (err) {
    const reason = err instanceof ApiError ? err.message : "Could not upload this file.";
    return { kind: "failed", key, name: file.name, reason };
  }
}

function replaced(items: Attachment[], next: Attachment): Attachment[] {
  return items.map((item) => (item.key === next.key ? next : item));
}

/** The files on the composer, each uploaded the moment it is added. */
export function useAttachments(chatId: string): Attachments {
  const [items, setItems] = useState<Attachment[]>([]);
  const nextKey = useRef(0);

  const add = useCallback(
    (files: File[]) => {
      for (const file of files) {
        const key = nextKey.current++;
        setItems((current) => [...current, { kind: "uploading", key, name: file.name }]);
        void uploadAttachment(chatId, file, key).then((next) =>
          setItems((current) => replaced(current, next)),
        );
      }
    },
    [chatId],
  );

  const remove = useCallback((key: number) => {
    setItems((current) => current.filter((item) => item.key !== key));
  }, []);

  const clear = useCallback(() => setItems([]), []);

  const uploading = useMemo(() => items.some((item) => item.kind === "uploading"), [items]);
  const uploaded = useMemo(
    () => items.flatMap((item) => (item.kind === "uploaded" ? [item.stored] : [])),
    [items],
  );

  return { items, uploading, uploaded, add, remove, clear };
}
