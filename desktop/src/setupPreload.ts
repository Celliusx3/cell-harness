import { contextBridge, ipcRenderer } from "electron";

import type { Answers, Endpoint } from "./setup";
import type { SaveResult } from "./setupWindow";

export interface CellSetup {
  readonly defaults: () => Promise<Endpoint>;
  readonly save: (answers: Answers) => Promise<SaveResult>;
}

// A sandboxed preload can require only "electron", so the channel names are spelled here and in setupWindow.ts.
const cellSetup: CellSetup = {
  defaults: () => ipcRenderer.invoke("setup:defaults"),
  save: (answers) => ipcRenderer.invoke("setup:save", answers),
};

contextBridge.exposeInMainWorld("cellSetup", cellSetup);
