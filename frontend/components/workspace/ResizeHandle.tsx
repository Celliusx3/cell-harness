"use client";

import { type KeyboardEvent, type PointerEvent, useRef } from "react";

import { CHAT_WIDTH_STEP, clampChatWidth, MIN_CHAT_WIDTH } from "@/components/workspace/chatWidth";

const STEP_OF_KEY = new Map([
  ["ArrowLeft", -CHAT_WIDTH_STEP],
  ["ArrowRight", CHAT_WIDTH_STEP],
]);

function rowWidthOf(handle: HTMLElement): number {
  return handle.parentElement?.getBoundingClientRect().width ?? 0;
}

interface ResizeHandleProps {
  width: number;
  onResize: (width: number) => void;
}

/** The bar between the chat and the files pane: drag it, or press the arrow keys, to resize the chat. */
export function ResizeHandle({ width, onResize }: ResizeHandleProps) {
  const drag = useRef<{ startX: number; startWidth: number } | null>(null);

  function handlePointerDown(event: PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    event.currentTarget.focus();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { startX: event.clientX, startWidth: width };
  }

  function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
    if (drag.current === null) return;
    const wanted = drag.current.startWidth + event.clientX - drag.current.startX;
    onResize(clampChatWidth(wanted, rowWidthOf(event.currentTarget)));
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const step = STEP_OF_KEY.get(event.key);
    if (step === undefined) return;
    event.preventDefault();
    onResize(clampChatWidth(width + step, rowWidthOf(event.currentTarget)));
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize the chat"
      aria-valuenow={width}
      aria-valuemin={MIN_CHAT_WIDTH}
      tabIndex={0}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={() => (drag.current = null)}
      onPointerCancel={() => (drag.current = null)}
      onKeyDown={handleKeyDown}
      className="group hidden w-2 shrink-0 cursor-col-resize touch-none items-center justify-center bg-surface outline-none focus-visible:bg-accent-soft lg:flex"
    >
      <span aria-hidden className="h-10 w-[3px] rounded-full bg-line transition group-hover:bg-ink-soft group-focus-visible:bg-accent" />
    </div>
  );
}
