import { watch } from "node:fs";
import path from "node:path";

const SETTLE_MS = 500;

/** Whether a change the folder reported is the settings file itself. */
export function isSettingsChange(changedName: string | null, settingsFile: string): boolean {
  return changedName === path.basename(settingsFile);
}

/** Calls back once the settings file settles after a change; returns the way to stop watching. */
export function watchSettings(settingsFile: string, onChange: () => void): () => void {
  let settleTimer: NodeJS.Timeout | null = null;
  const watcher = watch(path.dirname(settingsFile), (_event, changedName) => {
    if (!isSettingsChange(changedName, settingsFile)) return;
    if (settleTimer !== null) clearTimeout(settleTimer);
    settleTimer = setTimeout(() => {
      settleTimer = null;
      onChange();
    }, SETTLE_MS);
  });
  return () => {
    if (settleTimer !== null) clearTimeout(settleTimer);
    watcher.close();
  };
}
