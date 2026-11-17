import { isWithin } from "@/components/workspace/workspace";

/** A file opened in the files pane, by its path relative to the workspace. */
export interface FileTab {
  path: string;
  name: string;
}

/** The opened files, in tab order, and the one shown; null shows Browse. */
export interface Tabs {
  open: FileTab[];
  selected: string | null;
}

export const NO_TABS: Tabs = { open: [], selected: null };

/** `tab` opened and shown; an already open tab is only shown. */
export function openTab(tabs: Tabs, tab: FileTab): Tabs {
  const isOpen = tabs.open.some((each) => each.path === tab.path);
  return { open: isOpen ? tabs.open : [...tabs.open, tab], selected: tab.path };
}

/** The tab at `path` closed; when it was shown, its neighbour is, or Browse when none is left. */
export function closeTab(tabs: Tabs, path: string): Tabs {
  const at = tabs.open.findIndex((tab) => tab.path === path);
  if (at === -1) return tabs;
  const open = tabs.open.filter((tab) => tab.path !== path);
  if (tabs.selected !== path) return { open, selected: tabs.selected };
  const neighbour = open[Math.min(at, open.length - 1)];
  return { open, selected: neighbour === undefined ? null : neighbour.path };
}

/** Every tab at `path` or inside it closed, as `closeTab` closes one. */
export function closeTabsWithin(tabs: Tabs, path: string): Tabs {
  return tabs.open
    .filter((tab) => isWithin(tab.path, path))
    .reduce((left, tab) => closeTab(left, tab.path), tabs);
}
