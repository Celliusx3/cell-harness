import path from "node:path";

import { BrowserWindow, ipcMain } from "electron";

import { messageOf } from "./errors";
import { APP_NAME } from "./paths";
import {
  checkAnswers,
  formDefaults,
  newEncryptionKey,
  readLocalSettings,
  withSetup,
  writeLocalSettings,
  type Endpoint,
} from "./setup";

export type SaveResult = { readonly ok: true } | { readonly ok: false; readonly error: string };

export interface SetupInput {
  readonly localJson: string;
  readonly committed: Endpoint;
}

const SETUP_WINDOW_SIZE = { width: 460, height: 400 } as const;
const SETUP_PAGE = path.join(__dirname, "..", "src", "setup.html");
const SETUP_PRELOAD = path.join(__dirname, "setupPreload.js");
const DEFAULTS_CHANNEL = "setup:defaults";
const SAVE_CHANNEL = "setup:save";

/** Shows the setup form; resolves true once its answers are saved, and false when the window is closed first. */
export function askForSetup(input: SetupInput): Promise<boolean> {
  return new Promise((resolve, reject) => {
    const window = openSetupWindow();
    window.once("closed", () => {
      ipcMain.removeHandler(DEFAULTS_CHANNEL);
      ipcMain.removeHandler(SAVE_CHANNEL);
      resolve(false);
    });
    ipcMain.handle(DEFAULTS_CHANNEL, () => formDefaults(readLocalSettings(input.localJson), input.committed));
    ipcMain.handle(SAVE_CHANNEL, (_event, raw: unknown) => {
      const result = saveAnswers(input, raw);
      if (result.ok) {
        resolve(true);
        window.close();
      }
      return result;
    });
    window.loadFile(SETUP_PAGE).catch((error: unknown) => {
      reject(error);
      window.destroy();
    });
  });
}

function openSetupWindow(): BrowserWindow {
  const window = new BrowserWindow({
    ...SETUP_WINDOW_SIZE,
    title: `Set up ${APP_NAME}`,
    resizable: false,
    show: false,
    webPreferences: { preload: SETUP_PRELOAD, contextIsolation: true, sandbox: true, nodeIntegration: false },
  });
  window.once("ready-to-show", () => window.show());
  window.webContents.on("will-navigate", (event) => event.preventDefault());
  return window;
}

function saveAnswers(input: SetupInput, raw: unknown): SaveResult {
  try {
    const answers = checkAnswers(raw);
    const settings = withSetup(readLocalSettings(input.localJson), answers, input.committed, newEncryptionKey);
    writeLocalSettings(input.localJson, settings);
    return { ok: true };
  } catch (error) {
    return { ok: false, error: messageOf(error) };
  }
}
