import { spawn, type ChildProcess } from "node:child_process";
import { appendFileSync, closeSync, createWriteStream, existsSync, mkdirSync, openSync, readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";

import { app, BrowserWindow, dialog, session, shell, utilityProcess, type Session, type WebContents } from "electron";

import { APP_URL, isAppOrigin, isBrowserLink, isPermissionGranted } from "./origin";
import {
  APP_NAME,
  checkoutLayout,
  dataFiles,
  HARNESS_PORT,
  HOST,
  PAGES_PORT,
  userDataFolder,
  type DataFiles,
  type Layout,
} from "./paths";
import { harnessSpec, pagesSpec, waitForPort, type ChildSpec, type PagesSpec } from "./processes";

const HARNESS_START_MS = 60_000;
const PAGES_START_MS = 30_000;
const STOP_GRACE_MS = 10_000;
const LOG_TAIL_LINES = 20;
const START_FAILURE_TITLE = `${APP_NAME} could not start`;
const WINDOW_SIZE = { width: 1200, height: 820 } as const;

interface Child {
  readonly exited: Promise<void>;
  readonly stop: () => Promise<void>;
}

app.setPath("userData", userDataFolder(os.homedir()));

const files = dataFiles(app.getPath("userData"));
const layout = checkoutLayout(path.resolve(app.getAppPath(), ".."));

let children: readonly Child[] = [];
let stopping: Promise<void> | null = null;
let childrenStopped = false;

async function startApp(): Promise<void> {
  mkdirSync(path.dirname(files.harnessLog), { recursive: true });
  const missing = missingFileReason(layout, files);
  if (missing !== null) return failStart(missing);
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

/** Why the app cannot start yet, or null when every file it needs is there. */
function missingFileReason(layout: Layout, files: DataFiles): string | null {
  if (!existsSync(files.localJson)) {
    return `There is no settings file at ${files.localJson}. Write one with llm.api_key and secrets.encryption_key, then open the app again.`;
  }
  if (!existsSync(layout.pagesServer)) {
    return `The pages are not built: ${layout.pagesServer} is missing. Run \`npm run pages\` in desktop/, then start the app again.`;
  }
  return null;
}

/** Stops both children, says why the app could not start, and quits. */
async function failStart(message: string): Promise<void> {
  if (hasStopBegun()) return;
  await stopChildren();
  dialog.showErrorBox(START_FAILURE_TITLE, message);
  app.quit();
}

/** Starts the harness; stopping it ends its whole process group. */
function startHarness(spec: ChildSpec, logPath: string): Child {
  const child = spawnGroupLeader(spec, logPath);
  const exited = new Promise<void>((resolve) => {
    child.once("exit", () => resolve());
    child.once("error", (error) => {
      appendFileSync(logPath, `${error.message}\n`);
      resolve();
    });
  });
  const stop = async (): Promise<void> => {
    if (child.pid === undefined) return;
    signalGroup(child.pid, "SIGTERM");
    await graceForExit(exited);
    signalGroup(child.pid, "SIGKILL");
  };
  return { exited, stop };
}

/** Spawns the command as the leader of a new process group, its output appended to the log. */
function spawnGroupLeader(spec: ChildSpec, logPath: string): ChildProcess {
  const log = openSync(logPath, "a");
  const child = spawn(spec.command, [...spec.args], {
    cwd: spec.cwd,
    env: spec.env,
    detached: true,
    stdio: ["ignore", log, log],
  });
  closeSync(log);
  return child;
}

/** The page server runs on Electron's own Node, its output appended to the log. */
function startPages(spec: PagesSpec, logPath: string): Child {
  const child = utilityProcess.fork(spec.modulePath, [], { cwd: spec.cwd, env: spec.env, stdio: "pipe" });
  const log = createWriteStream(logPath, { flags: "a" });
  child.stdout?.pipe(log, { end: false });
  child.stderr?.pipe(log, { end: false });
  const exited = new Promise<void>((resolve) => child.once("exit", () => resolve()));
  const stop = async (): Promise<void> => {
    child.kill();
    await graceForExit(exited);
  };
  return { exited, stop };
}

/** Signals every process in the group; a group already gone is not an error. */
function signalGroup(leaderPid: number, signal: NodeJS.Signals): void {
  try {
    process.kill(-leaderPid, signal);
  } catch (error) {
    if (!isNoSuchProcess(error)) throw error;
  }
}

function isNoSuchProcess(error: unknown): boolean {
  return error instanceof Error && "code" in error && error.code === "ESRCH";
}

async function graceForExit(exited: Promise<void>): Promise<void> {
  const grace = new AbortController();
  const outcomes = [exited, delay(STOP_GRACE_MS, undefined, { signal: grace.signal })];
  await Promise.race(outcomes).finally(() => grace.abort());
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

function openWindow(): void {
  const window = new BrowserWindow({
    ...WINDOW_SIZE,
    title: APP_NAME,
    webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false },
  });
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

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

app.on("before-quit", handleBeforeQuit);
app.on("window-all-closed", () => app.quit());
app
  .whenReady()
  .then(() => {
    allowOnlyAppClipboardWrites(session.defaultSession);
    return startApp();
  })
  .catch((error: unknown) => failStart(messageOf(error)));
