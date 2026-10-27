import { watch } from "node:fs";
import path from "node:path";

const SETTLE_MS = 500;

/** Whether a change the folder reported is the settings file itself, not a save's temp file. */
export function isSettingsChange(changed: string | null, settingsFile: string): boolean {
  return changed === path.basename(settingsFile);
}

/** Calls back once the settings file settles after a change; returns the way to stop watching. */
export function watchSettings(settingsFile: string, onChange: () => void): () => void {
  let settling: NodeJS.Timeout | null = null;
  const watcher = watch(path.dirname(settingsFile), (_event, changed) => {
    if (!isSettingsChange(changed, settingsFile)) return;
    if (settling !== null) clearTimeout(settling);
    settling = setTimeout(() => {
      settling = null;
      onChange();
    }, SETTLE_MS);
  });
  return () => {
    if (settling !== null) clearTimeout(settling);
    watcher.close();
  };
}
