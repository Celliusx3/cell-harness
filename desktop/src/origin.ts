import { HOST, PAGES_PORT } from "./paths";

export const APP_URL = `http://${HOST}:${PAGES_PORT}`;

const APP_ORIGIN = new URL(APP_URL).origin;
const BROWSER_PROTOCOLS: ReadonlySet<string> = new Set(["http:", "https:"]);
const CLIPBOARD_WRITE = "clipboard-sanitized-write";

/** Whether the URL is one of the app's own pages. */
export function isAppOrigin(url: string): boolean {
  return URL.canParse(url) && new URL(url).origin === APP_ORIGIN;
}

/** Whether the default browser is the one to open the URL. */
export function isBrowserLink(url: string): boolean {
  return URL.canParse(url) && BROWSER_PROTOCOLS.has(new URL(url).protocol);
}

/** Whether a page at the URL is granted the permission: only a clipboard write from the app's own pages. */
export function isPermissionGranted(permission: string, url: string): boolean {
  return permission === CLIPBOARD_WRITE && isAppOrigin(url);
}
