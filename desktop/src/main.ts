import { existsSync, mkdirSync, readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

import { app, BrowserWindow, dialog, session, shell, type Session, type WebContents } from "electron";

import { startHarness, startPages, type Child } from "./children";
import { messageOf } from "./errors";
import { APP_URL, isAppOrigin, isBrowserLink, isPermissionGranted } from "./origin";
import { APP_NAME, checkoutLayout, dataFiles, HARNESS_PORT, HOST, PAGES_PORT, userDataFolder, type Layout } from "./paths";
import { harnessSpec, pagesSpec, waitForPort } from "./processes";
import { committedEndpoint, needsSetup, readLocalSettings } from "./setup";
import { askForSetup } from "./setupWindow";

const HARNESS_START_MS = 60_000;
const PAGES_START_MS = 30_000;
const LOG_TAIL_LINES = 20;
const START_FAILURE_TITLE = `${APP_NAME} could not start`;
const WINDOW_SIZE = { width: 1200, height: 820 } as const;

app.setPath("userData", userDataFolder(os.homedir()));

const files = dataFiles(app.getPath("userData"));
const layout = checkoutLayout(path.resolve(app.getAppPath(), ".."));

let children: readonly Child[] = [];
let stopping: Promise<void> | null = null;
let childrenStopped = false;
let hasChatWindowOpened = false;

async function startApp(): Promise<void> {
  mkdirSync(path.dirname(files.harnessLog), { recursive: true });
  const missing = missingPagesReason(layout);
  if (missing !== null) return failStart(missing);
  if (!(await askForApiKeyIfMissing())) return app.quit();
  const harness = startHarness(harnessSpec(layout, files, process.env), files.harnessLog);
  const pages = startPages(pagesSpec(layout, process.env), files.pagesLog);
  children = [harness, pages];
  try {
    await Promise.all([
      waitForPort({ host: HOST, port: HARNESS_PORT }, HARNESS_START_MS, harness.exited),
      waitForPort({ host: HOST, port: PAGES_PORT }, PAGES_START_MS, pages.exited),
    ]);
  } catch (error) {
    return failStart(`${messageOf(error)}\n\n${logTail(files.harnessLog)}`);
  }
  openWindow();
}

/** Why the app cannot start yet, or null when the pages are built. */
function missingPagesReason(layout: Layout): string | null {
  if (!existsSync(layout.pagesServer)) {
    return `The pages are not built: ${layout.pagesServer} is missing. Run \`npm run pages\` in desktop/, then start the app again.`;
  }
  return null;
}

/** True once the settings file holds an API key; false when the friend closed the setup window instead. */
async function askForApiKeyIfMissing(): Promise<boolean> {
  if (!needsSetup(readLocalSettings(files.localJson))) return true;
  const committed = committedEndpoint(readFileSync(layout.configJson, "utf8"));
  return askForSetup({ localJson: files.localJson, committed });
}

/** Stops both children, says why the app could not start, and quits. */
async function failStart(message: string): Promise<void> {
  if (hasStopBegun()) return;
  await stopChildren();
  dialog.showErrorBox(START_FAILURE_TITLE, message);
  app.quit();
}

function stopChildren(): Promise<void> {
  stopping ??= Promise.all(children.map((child) => child.stop())).then(() => undefined);
  return stopping;
}

function hasStopBegun(): boolean {
  return stopping !== null;
}

/** Holds every quit, Cmd-Q included, until both children have stopped. */
function handleBeforeQuit(event: Electron.Event): void {
  if (childrenStopped) return;
  event.preventDefault();
  void stopChildren().finally(() => {
    childrenStopped = true;
    app.quit();
  });
}

function quitIfChatWindowOpened(): void {
  if (hasChatWindowOpened) app.quit();
}

function openWindow(): void {
  const window = new BrowserWindow({
    ...WINDOW_SIZE,
    title: APP_NAME,
    webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false },
  });
  hasChatWindowOpened = true;
  keepLinksInTheBrowser(window.webContents);
  window.loadURL(APP_URL).catch((error: unknown) => dialog.showErrorBox(START_FAILURE_TITLE, messageOf(error)));
}

/** The window only shows the app's own pages; a link to another origin, and every new window, opens in the default browser. */
function keepLinksInTheBrowser(contents: WebContents): void {
  contents.on("will-navigate", (event) => {
    if (isAppOrigin(event.url)) return;
    event.preventDefault();
    openInBrowser(event.url);
  });
  contents.setWindowOpenHandler(({ url }) => {
    openInBrowser(url);
    return { action: "deny" };
  });
}

function openInBrowser(url: string): void {
  if (!isBrowserLink(url)) return;
  shell
    .openExternal(url)
    .catch((error: unknown) => dialog.showErrorBox(`${APP_NAME} could not open a link`, `${url}\n\n${messageOf(error)}`));
}

function allowOnlyAppClipboardWrites(ses: Session): void {
  ses.setPermissionRequestHandler((_contents, permission, callback, details) =>
    callback(isPermissionGranted(permission, details.requestingUrl)),
  );
  ses.setPermissionCheckHandler((_contents, permission, requestingOrigin) =>
    isPermissionGranted(permission, requestingOrigin),
  );
}

function logTail(logPath: string): string {
  return readFileSync(logPath, "utf8").trimEnd().split("\n").slice(-LOG_TAIL_LINES).join("\n");
}

app.on("before-quit", handleBeforeQuit);
app.on("window-all-closed", quitIfChatWindowOpened);
app
  .whenReady()
  .then(() => {
    allowOnlyAppClipboardWrites(session.defaultSession);
    return startApp();
  })
  .catch((error: unknown) => failStart(messageOf(error)));
