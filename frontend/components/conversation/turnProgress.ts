/** What the bot is doing while its turn shows nothing of its own yet. */

import type { Row } from "@/components/conversation/turnRows";

export type Progress = { kind: "thinking" };

export function progressOf(
  rows: Row[],
  openTurn: number | null,
  sending: string | null,
): Progress | null {
  if (sending === null && openTurn === null) return null;
  const answered = rows.some((row) => row.kind === "answer" && row.turn === openTurn);
  return answered ? null : { kind: "thinking" };
}
