import { APP_NAME, HARNESS_PORT } from "./paths";
import { HARNESS_APP_FACTORY } from "./processes";

export interface PidRecord {
  readonly harnessPid: number;
}

const PORT_FLAG = "--port";

/** The pid file's text, recording the harness this run started. */
export function pidFileText(harnessPid: number): string {
  return `${JSON.stringify({ harnessPid } satisfies PidRecord)}\n`;
}

/** The recorded pid, or null when the file is not one this app wrote. */
export function parsePidFile(text: string): PidRecord | null {
  const parsed = parsedJson(text);
  if (typeof parsed !== "object" || parsed === null || !("harnessPid" in parsed)) return null;
  const pid = parsed.harnessPid;
  return isPositiveInteger(pid) ? { harnessPid: pid } : null;
}

/** Whether the recorded pid's live command line, or null when it is not alive, is our harness on our port. */
export function isOurHarness(command: string | null): boolean {
  if (command === null) return false;
  const words = command.trim().split(/\s+/);
  return words.includes(HARNESS_APP_FACTORY) && words.some((word, i) => isOurPortFlag(word, words[i + 1]));
}

/** Why the app cannot start while another program holds one of its ports. */
export function portInUseReason(port: number): string {
  return `Port ${port} is in use by another program. Quit it, then open ${APP_NAME} again.`;
}

function parsedJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch (error) {
    if (error instanceof SyntaxError) return null;
    throw error;
  }
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function isOurPortFlag(word: string, next: string | undefined): boolean {
  return word === PORT_FLAG && next === String(HARNESS_PORT);
}
