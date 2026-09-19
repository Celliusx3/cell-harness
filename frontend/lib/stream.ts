import type { SessionEvent } from "./types";

/** Reading the SSE stream with `fetch`. */

/** Why the stream stopped, which decides whether the caller reconnects. */
export type StreamEnd =
  | { kind: "end" }
  | { kind: "dropped" }
  | { kind: "aborted" };

export interface StreamHandlers {
  onEvent(event: SessionEvent): void;
  onEnd(end: StreamEnd): void;
}

/** Stream a conversation's events from `after`. */
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
    if (line.startsWith(":")) continue; // an SSE comment line
    if (line.startsWith("event: ")) event = line.slice(7);
    else if (line.startsWith("data: ")) data.push(line.slice(6));
  }
  return data.length ? { event, data: data.join("\n") } : null;
}
