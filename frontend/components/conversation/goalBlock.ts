/** The block a goal run's lead ends its reply with: kept in the log, never shown in the chat. */

const OPEN = "<goal>";
const BLOCK = /<goal>[\s\S]*?<\/goal>/g;

/** `text` as the chat shows it: without any `<goal>` block, nor one still arriving at its end. */
export function withoutGoalBlocks(text: string): string {
  const closed = text.replace(BLOCK, "");
  const open = closed.indexOf(OPEN);
  return (open < 0 ? closed : closed.slice(0, open)).trim();
}
