import path from "node:path";

export const APP_NAME = "Cell Harness";
export const HOST = "127.0.0.1";
export const HARNESS_PORT = 4886;
export const PAGES_PORT = 4887;

export interface Command {
  readonly command: string;
  readonly args: readonly string[];
}

export interface Layout {
  readonly python: Command;
  readonly backendDir: string;
  readonly configJson: string;
  readonly pagesServer: string;
  readonly extraPath: readonly string[];
  readonly pythonPath: readonly string[];
  readonly writesBytecode: boolean;
}

export interface DataFiles {
  readonly folder: string;
  readonly localJson: string;
  readonly harnessLog: string;
  readonly pagesLog: string;
  readonly pidFile: string;
}

/** The app's data folder, under Application Support in the home folder. */
export function userDataFolder(home: string): string {
  return path.join(home, "Library", "Application Support", APP_NAME);
}

/** The files the app keeps in its data folder. */
export function dataFiles(folder: string): DataFiles {
  const logs = path.join(folder, "logs");
  return {
    folder,
    localJson: path.join(folder, "config.local.json"),
    harnessLog: path.join(logs, "harness.log"),
    pagesLog: path.join(logs, "pages.log"),
    pidFile: path.join(folder, "harness.pid"),
  };
}

/** Where the programs are when the app runs from a checkout of the repo. */
export function checkoutLayout(repoRoot: string): Layout {
  const desktop = path.join(repoRoot, "desktop");
  return {
    python: { command: "uv", args: ["run", "--quiet", "python"] },
    backendDir: path.join(repoRoot, "backend"),
    configJson: path.join(desktop, "config.json"),
    pagesServer: path.join(desktop, "build", "pages", "server.js"),
    extraPath: [],
    pythonPath: [],
    writesBytecode: true,
  };
}

/** Where the programs are inside the packaged app's Resources folder. */
export function packagedLayout(resources: string): Layout {
  const backendDir = path.join(resources, "app", "backend");
  return {
    python: { command: path.join(resources, "python", "bin", "python3"), args: [] },
    backendDir,
    configJson: path.join(resources, "app", "desktop", "config.json"),
    pagesServer: path.join(resources, "pages", "server.js"),
    extraPath: [path.join(resources, "bin")],
    pythonPath: [backendDir, path.join(resources, "site-packages")],
    writesBytecode: false,
  };
}
