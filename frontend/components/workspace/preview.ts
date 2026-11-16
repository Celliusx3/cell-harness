export const TEXT_PREVIEW_BYTES = 256 * 1024;

const NUL = 0;

export interface Head {
  bytes: Uint8Array;
  cut: boolean;
}

/** The first `limit` bytes of `chunks`, and whether anything was left past them. */
export function headOf(chunks: Uint8Array[], limit: number): Head {
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const bytes = new Uint8Array(Math.min(total, limit));
  let at = 0;
  for (const chunk of chunks) {
    if (at >= bytes.length) break;
    const taken = chunk.subarray(0, bytes.length - at);
    bytes.set(taken, at);
    at += taken.length;
  }
  return { bytes, cut: total > limit };
}

/** The head as text, or null when it holds a NUL byte or is not UTF-8; a character split by the cut is dropped. */
export function textOf(head: Head): string | null {
  if (head.bytes.includes(NUL)) return null;
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(head.bytes, { stream: head.cut });
  } catch {
    return null;
  }
}
