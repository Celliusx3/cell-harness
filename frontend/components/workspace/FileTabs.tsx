"use client";

import { FolderIcon, XIcon } from "lucide-react";

import type { Tabs } from "@/components/workspace/tabs";

const TAB = "flex h-[34px] shrink-0 items-center gap-2 rounded-t-lg border border-b-0 px-3 transition";
const SELECTED = `${TAB} -mb-px border-line bg-surface-raised font-medium text-ink`;
const UNSELECTED = `${TAB} border-transparent text-ink-soft hover:text-ink`;

interface FileTabsProps {
  tabs: Tabs;
  onSelect: (path: string | null) => void;
  onClose: (path: string) => void;
}

/** "Browse", then one tab per opened file, each with its close button. */
export function FileTabs({ tabs, onSelect, onClose }: FileTabsProps) {
  return (
    <div
      role="tablist"
      aria-label="Open files"
      className="flex h-11 shrink-0 items-end gap-0.5 overflow-x-auto border-b border-line bg-surface px-2"
    >
      <button
        type="button"
        role="tab"
        aria-selected={tabs.selected === null}
        onClick={() => onSelect(null)}
        className={tabs.selected === null ? SELECTED : UNSELECTED}
      >
        <FolderIcon className="size-3.5" aria-hidden />
        Browse
      </button>
      {tabs.open.map((tab) => (
        <div key={tab.path} className={tabs.selected === tab.path ? SELECTED : UNSELECTED}>
          <button
            type="button"
            role="tab"
            aria-selected={tabs.selected === tab.path}
            title={tab.path}
            onClick={() => onSelect(tab.path)}
            className="whitespace-nowrap"
          >
            {tab.name}
          </button>
          <button
            type="button"
            aria-label={`Close ${tab.name}`}
            onClick={() => onClose(tab.path)}
            className="flex size-[18px] items-center justify-center rounded text-ink-soft hover:bg-surface-sunken hover:text-ink"
          >
            <XIcon className="size-3" aria-hidden />
          </button>
        </div>
      ))}
    </div>
  );
}
