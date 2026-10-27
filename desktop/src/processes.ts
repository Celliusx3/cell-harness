import { connect } from "node:net";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";

import { HARNESS_PORT, HOST, PAGES_PORT, type DataFiles, type Layout } from "./paths";
import { HARNESS_MARKER } from "./strays";

export interface ChildSpec {
  readonly command: string;
  readonly args: readonly string[];
  readonly cwd: string;
  readonly env: Readonly<Record<string, string>>;
}

export interface PagesSpec {
  readonly modulePath: string;
  readonly cwd: string;
  readonly env: Readonly<Record<string, string>>;
}

export interface Target {
  readonly host: string;
  readonly port: number;
}

const HARNESS_SETTING_PREFIX = "HARNESS_";
const RETRY_MS = 200;

/** How the harness is started: uvicorn on this Mac only, reading the app's two settings files. */
export function harnessSpec(layout: Layout, files: DataFiles, baseEnv: NodeJS.ProcessEnv): ChildSpec {
  return {
    command: layout.python.command,
    args: [
      ...layout.python.args,
      "-m",
      "uvicorn",
      HARNESS_MARKER,
      "--factory",
      "--host",
      HOST,
      "--port",
      String(HARNESS_PORT),
    ],
    cwd: layout.backendDir,
    env: {
      ...inheritedEnv(baseEnv),
      HARNESS_CONFIG: layout.configJson,
      HARNESS_CONFIG_LOCAL: files.localJson,
      PATH: searchPath(layout.extraPath, baseEnv.PATH),
      ...pythonPathEnv(layout.pythonPath),
      ...layout.harnessEnv,
    },
  };
}

/** How the page server is started: Next's standalone server on this Mac only. */
export function pagesSpec(layout: Layout, baseEnv: NodeJS.ProcessEnv): PagesSpec {
  return {
    modulePath: layout.pagesServer,
    cwd: path.dirname(layout.pagesServer),
    env: {
      ...inheritedEnv(baseEnv),
      PORT: String(PAGES_PORT),
      HOSTNAME: HOST,
      NODE_ENV: "production",
    },
  };
}

/** Resolves once the target accepts a connection, and rejects on timeout or when the program exits. */
export function waitForPort(target: Target, timeoutMs: number, exited: Promise<unknown>): Promise<void> {
  const address = `${target.host}:${target.port}`;
  const stopPolling = new AbortController();
  const exitedFirst = (): never => {
    throw new Error(`the program exited before ${address} answered`);
  };
  const late = delay(timeoutMs, undefined, { signal: stopPolling.signal }).then(() => {
    throw new Error(`${address} did not answer within ${timeoutMs} ms`);
  });
  const outcomes = [pollUntilOpen(target, stopPolling.signal), late, exited.then(exitedFirst, exitedFirst)];
  return Promise.race(outcomes).finally(() => stopPolling.abort());
}

/** The first of the ports that already accepts a connection on the host, or null when every one is free. */
export async function firstPortInUse(host: string, ports: readonly number[]): Promise<number | null> {
  for (const port of ports) {
    if (await isListening({ host, port })) return port;
  }
  return null;
}

/** The parent's environment without unset keys or a harness setting. */
function inheritedEnv(baseEnv: NodeJS.ProcessEnv): Record<string, string> {
  return Object.fromEntries(
    Object.entries(baseEnv).filter(
      (entry): entry is [string, string] => entry[1] !== undefined && !isHarnessSetting(entry[0]),
    ),
  );
}

/** Whether the harness reads the key as a setting: the prefix in any case. */
function isHarnessSetting(key: string): boolean {
  return key.toUpperCase().startsWith(HARNESS_SETTING_PREFIX);
}

function searchPath(extraPath: readonly string[], basePath: string | undefined): string {
  return [...extraPath, ...(basePath === undefined ? [] : [basePath])].join(":");
}

function pythonPathEnv(pythonPath: readonly string[]): Record<string, string> {
  return pythonPath.length === 0 ? {} : { PYTHONPATH: pythonPath.join(":") };
}

async function pollUntilOpen(target: Target, signal: AbortSignal): Promise<void> {
  while (!(await isListening(target))) {
    await delay(RETRY_MS, undefined, { signal });
  }
}

function isListening(target: Target): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = connect(target.port, target.host);
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("error", () => {
      socket.destroy();
      resolve(false);
    });
  });
}
