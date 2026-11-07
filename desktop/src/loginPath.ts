import { spawn } from "node:child_process";

import { messageOf } from "./errors";

export const PATH_START_MARKER = "__CELL_HARNESS_PATH_START__";
export const PATH_END_MARKER = "__CELL_HARNESS_PATH_END__";
export const LOGIN_SHELL_TIMEOUT_MS = 5_000;

const FALLBACK_SHELL = "/bin/zsh";

/** Runs the program with stdin closed and no TTY, and resolves with its stdout once it exits 0 within the time limit. */
export type ShellRunner = (shell: string, args: readonly string[], timeoutMs: number) => Promise<string>;

export type BasePath =
  | { readonly source: "login-shell"; readonly path: string }
  | { readonly source: "inherited"; readonly path: string | undefined; readonly reason: string };

/** The user's login shell, or zsh, the macOS default, when SHELL is unset or not an absolute path. */
export function loginShell(shellSetting: string | undefined): string {
  return shellSetting !== undefined && shellSetting.startsWith("/") ? shellSetting : FALLBACK_SHELL;
}

/** Arguments that make the shell read the user's profile as Terminal does, then print PATH between the markers. */
export function loginShellArgs(): readonly string[] {
  return ["-l", "-i", "-c", `printf '%s%s%s' '${PATH_START_MARKER}' "$PATH" '${PATH_END_MARKER}'`];
}

/** The PATH printed between the markers; refuses output with no markers or an empty PATH between them. */
export function parseMarkedPath(output: string): string {
  const start = output.indexOf(PATH_START_MARKER);
  const end = start === -1 ? -1 : output.indexOf(PATH_END_MARKER, start + PATH_START_MARKER.length);
  if (end === -1) throw new Error("the login shell printed no PATH markers");
  const found = output.slice(start + PATH_START_MARKER.length, end).trim();
  if (found === "") throw new Error("the login shell printed an empty PATH");
  return found;
}

/** The base PATH for the harness: the login shell's, or the inherited one with the reason the shell could not give it. */
export async function harnessBasePath(env: NodeJS.ProcessEnv, run: ShellRunner): Promise<BasePath> {
  const shell = loginShell(env.SHELL);
  try {
    const output = await run(shell, loginShellArgs(), LOGIN_SHELL_TIMEOUT_MS);
    return { source: "login-shell", path: parseMarkedPath(output) };
  } catch (error) {
    return { source: "inherited", path: env.PATH, reason: `${shell}: ${messageOf(error)}` };
  }
}

/** Runs a program for its stdout in its own process group; an interactive shell ignores SIGTERM, so the time limit kills the group. */
export function runShell(shell: string, args: readonly string[], timeoutMs: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(shell, [...args], { stdio: ["ignore", "pipe", "ignore"], detached: true });
    const chunks: Buffer[] = [];
    const timer = setTimeout(() => {
      killGroup(child.pid);
      reject(new Error(`no answer within ${timeoutMs} ms`));
    }, timeoutMs);
    child.stdout.on("data", (chunk: Buffer) => chunks.push(chunk));
    child.once("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.once("close", (code, signal) => {
      clearTimeout(timer);
      if (code === 0) resolve(Buffer.concat(chunks).toString("utf8"));
      else reject(new Error(`exited with ${code ?? signal}`));
    });
  });
}

function killGroup(leaderPid: number | undefined): void {
  if (leaderPid === undefined) return;
  try {
    process.kill(-leaderPid, "SIGKILL");
  } catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "ESRCH")) throw error;
  }
}
