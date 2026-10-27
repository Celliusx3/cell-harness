import { app, dialog, Menu, nativeImage, shell, Tray, type NativeImage } from "electron";

import { messageOf } from "./errors";
import { APP_URL } from "./origin";
import { APP_NAME } from "./paths";
import { TRAY_ICON_POINTS, trayIconPixels } from "./trayIcon";
import { trayMenu } from "./trayMenu";

export interface TrayInput {
  readonly showChatWindow: () => void;
  readonly showCredentials: () => void;
  readonly settingsFile: string;
}

const ICON_SCALES = [1, 2] as const;

/** Adds the menu-bar icon and its menu. */
export function addTray(input: TrayInput): Tray {
  const tray = new Tray(templateTrayImage());
  tray.setToolTip(APP_NAME);
  tray.setContextMenu(
    Menu.buildFromTemplate(
      trayMenu({
        showChatWindow: input.showChatWindow,
        showCredentials: input.showCredentials,
        openInBrowser: openAppInBrowser,
        showSettingsFile: () => shell.showItemInFolder(input.settingsFile),
        quit: () => app.quit(),
      }),
    ),
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
