const SAVED_PATH = "harness:chat-path";
const HOME = "/";
const SETTINGS = "/settings";
const PATH_ON_THIS_APP = /^\/(?![/\\])/;

/** The saved path when it is a page of this app outside Settings, or the home page. */
export function returnPathOf(saved: string | null): string {
  if (saved === null || !PATH_ON_THIS_APP.test(saved)) return HOME;
  if (saved === SETTINGS || saved.startsWith(`${SETTINGS}/`)) return HOME;
  return saved;
}

/** Keeps the chat page open now, for Settings' way back, in this tab only. */
export function rememberChatPath(path: string): void {
  try {
    window.sessionStorage.setItem(SAVED_PATH, path);
  } catch {
    return;
  }
}

/** The chat page this tab left for Settings, or the home page. */
export function chatPathToReturnTo(): string {
  return returnPathOf(savedPath());
}

function savedPath(): string | null {
  try {
    return window.sessionStorage.getItem(SAVED_PATH);
  } catch {
    return null;
  }
}
