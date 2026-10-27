import { contextBridge, ipcRenderer } from "electron";

import type { Answers, Endpoint } from "./setup";
import type { SaveResult, SetupChannel } from "./setupWindow";

export interface CellSetup {
  readonly defaults: () => Promise<Endpoint>;
  readonly save: (answers: Answers) => Promise<SaveResult>;
}

const DEFAULTS: SetupChannel = "setup:defaults";
const SAVE: SetupChannel = "setup:save";

const cellSetup: CellSetup = {
  defaults: () => ipcRenderer.invoke(DEFAULTS),
  save: (answers) => ipcRenderer.invoke(SAVE, answers),
};

contextBridge.exposeInMainWorld("cellSetup", cellSetup);
