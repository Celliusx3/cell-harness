import { app, dialog, Menu, nativeImage, shell, Tray, type NativeImage } from "electron";

import { messageOf } from "./errors";
import { APP_URL } from "./origin";
import { APP_NAME } from "./paths";
import { TRAY_ICON_POINTS, trayIconPixels } from "./trayIcon";

export interface TrayInput {
  readonly showChatWindow: () => void;
  readonly settingsFile: string;
}

const ICON_SCALES = [1, 2] as const;

/** Adds the menu-bar icon and its menu. */
export function addTray(input: TrayInput): Tray {
  const tray = new Tray(templateTrayImage());
  tray.setToolTip(APP_NAME);
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: `Open ${APP_NAME}`, click: input.showChatWindow },
      { label: "Open in Browser", click: openAppInBrowser },
      { label: "Show Settings File", click: () => shell.showItemInFolder(input.settingsFile) },
      { type: "separator" },
      { label: `Quit ${APP_NAME}`, click: () => app.quit() },
    ]),
  );
  return tray;
}

function templateTrayImage(): NativeImage {
  const image = nativeImage.createEmpty();
  for (const scaleFactor of ICON_SCALES) {
    const size = TRAY_ICON_POINTS * scaleFactor;
    image.addRepresentation({ scaleFactor, width: size, height: size, buffer: trayIconPixels(scaleFactor) });
  }
  image.setTemplateImage(true);
  return image;
}

function openAppInBrowser(): void {
  shell
    .openExternal(APP_URL)
    .catch((error: unknown) => dialog.showErrorBox(`${APP_NAME} could not open the browser`, messageOf(error)));
}
