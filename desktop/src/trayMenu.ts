import type { MenuItemConstructorOptions } from "electron";

import { APP_NAME } from "./paths";

export interface TrayActions {
  readonly showChatWindow: () => void;
  readonly showCredentials: () => void;
  readonly openInBrowser: () => void;
  readonly showSettingsFile: () => void;
  readonly quit: () => void;
}

/** The menu-bar icon's menu, in order. */
export function trayMenu(actions: TrayActions): MenuItemConstructorOptions[] {
  return [
    { label: `Open ${APP_NAME}`, click: actions.showChatWindow },
    { label: "Credentials…", click: actions.showCredentials },
    { label: "Open in Browser", click: actions.openInBrowser },
    { label: "Show Settings File", click: actions.showSettingsFile },
    { type: "separator" },
    { label: `Quit ${APP_NAME}`, click: actions.quit },
  ];
}
