import type { SessionEvent } from "./types";

/**
 * Reading the SSE stream with `fetch`, deliberately not `EventSource`.
 *
 * `EventSource` reconnects on its own using `Last-Event-ID`, which we would have
 * to implement server-side, and its retry would race the cursor this whole design
 * is built around. Reading the body by hand keeps the caller's cursor the single
 * answer to "where am I", which is exactly what makes refresh-mid-turn work.
 *
 * It also cannot send a cursor on reconnect, cannot be aborted precisely, and
 * treats a clean end as a reason to reconnect — three things we need the opposite
 * of.
 */

/** Why the stream stopped, which decides whether the caller reconnects. */
export type StreamEnd =
  | { kind: "end" } // the server said `end`: the turn is over, stop
  | { kind: "dropped" } // the body ended without `end`: reconnect at the cursor
  | { kind: "aborted" }; // we closed it deliberately (navigation, unmount)

export interface StreamHandlers {
  onEvent(event: SessionEvent): void;
  onEnd(end: StreamEnd): void;
}

/**
 * Stream a conversation's events from `after`.
 *
 * Events are delivered one at a time in log order. The caller advances its own
 * cursor as they arrive, so a `dropped` ending can be resumed with no gap.
 */
export async function streamEvents(
  conversationId: string,
  after: number,
  signal: AbortSignal,
  handlers: StreamHandlers,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`/api/conversations/${conversationId}/events?after=${after}`, {
      signal,
      headers: { accept: "text/event-stream" },
    });
  } catch {
    handlers.onEnd(signal.aborted ? { kind: "aborted" } : { kind: "dropped" });
    return;
  }

  if (!response.ok || !response.body) {
    handlers.onEnd({ kind: "dropped" });
    return;
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  let sawEnd = false;

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += value;

      // Frames are separated by a blank line. A partial frame stays in the
      // buffer — a chunk boundary can fall anywhere, including mid-JSON.
      let split: number;
      while ((split = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        const frame = parseFrame(block);
        if (!frame) continue;
        if (frame.event === "end") {
          sawEnd = true;
        } else if (frame.event === "session") {
          handlers.onEvent(JSON.parse(frame.data) as SessionEvent);
        }
      }
      if (sawEnd) break;
    }
  } catch {
    // An aborted read lands here; so does a genuine network fault. The
    // distinction is the signal, not the exception.
  } finally {
    await reader.cancel().catch(() => {});
  }

  if (signal.aborted) handlers.onEnd({ kind: "aborted" });
  else handlers.onEnd(sawEnd ? { kind: "end" } : { kind: "dropped" });
}

function parseFrame(block: string): { event: string; data: string } | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue; // a comment, e.g. a future keepalive
    if (line.startsWith("event: ")) event = line.slice(7);
    else if (line.startsWith("data: ")) data.push(line.slice(6));
  }
  return data.length ? { event, data: data.join("\n") } : null;
}
