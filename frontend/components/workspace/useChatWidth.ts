"use client";

import { useCallback, useEffect, useState } from "react";

import { DEFAULT_CHAT_WIDTH, keptChatWidth } from "@/components/workspace/chatWidth";

const KEY = "cell-harness.files.chat-width";

function readKept(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function keep(width: number): void {
  try {
    window.localStorage.setItem(KEY, String(width));
  } catch {
    return;
  }
}

/** The chat's width beside the files pane, as this browser last kept it. */
export function useChatWidth(): { width: number; resize: (width: number) => void } {
  const [width, setWidth] = useState(DEFAULT_CHAT_WIDTH);

  useEffect(() => {
    setWidth(keptChatWidth(readKept()));
  }, []);

  const resize = useCallback((next: number) => {
    setWidth(next);
    keep(next);
  }, []);

  return { width, resize };
}
