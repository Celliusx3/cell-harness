export const DEFAULT_CHAT_WIDTH = 450;
export const MIN_CHAT_WIDTH = 400;
const MIN_FILES_WIDTH = 320;
const HANDLE_WIDTH = 8;
export const CHAT_WIDTH_STEP = 16;

/** The widest the chat may be in a row `rowWidth` wide, leaving the files pane its least. */
function widestChat(rowWidth: number): number {
  return Math.max(MIN_CHAT_WIDTH, rowWidth - MIN_FILES_WIDTH - HANDLE_WIDTH);
}

/** `wanted` held between the chat's least width and the widest a row `rowWidth` wide allows. */
export function clampChatWidth(wanted: number, rowWidth: number): number {
  return Math.round(Math.min(Math.max(wanted, MIN_CHAT_WIDTH), widestChat(rowWidth)));
}

/** The width a browser kept, or the default when it kept none or nothing usable. */
export function keptChatWidth(kept: string | null): number {
  const width = Number(kept);
  return kept !== null && Number.isFinite(width) && width >= MIN_CHAT_WIDTH ? width : DEFAULT_CHAT_WIDTH;
}
