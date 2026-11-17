"use client";

import { type ReactNode, useState } from "react";

import type { WorkspaceChoice } from "@/components/workspace/choices";
import { FileTabs } from "@/components/workspace/FileTabs";
import { FileView } from "@/components/workspace/FileView";
import { closeTab, closeTabsWithin, NO_TABS, openTab, type Tabs } from "@/components/workspace/tabs";
import { entryAt } from "@/components/workspace/tree";
import { useWorkspaceTree } from "@/components/workspace/useWorkspaceTree";
import { absolutePath, parentPath } from "@/components/workspace/workspace";
import { type TreeActions, WorkspaceTree } from "@/components/workspace/WorkspaceTree";
import { fileUrl } from "@/lib/api";

interface WorkspaceFilesProps {
  choice: WorkspaceChoice;
  switcher: ReactNode;
}

/** One workspace in the files pane: its tabs, its tree, and the opened file. */
export function WorkspaceFiles({ choice, switcher }: WorkspaceFilesProps) {
  const files = useWorkspaceTree(choice.chatId);
  const [tabs, setTabs] = useState<Tabs>(NO_TABS);
  const shownTab = tabs.open.find((tab) => tab.path === tabs.selected);
  const { workspace } = files;
  const urlOf =
    workspace === null
      ? null
      : (path: string) => fileUrl({ kind: "chat", id: choice.chatId }, absolutePath(workspace, path));

  const deleteEntry = (path: string) => {
    void files.deleteEntry(path).then((isDeleted) => {
      if (isDeleted) setTabs((current) => closeTabsWithin(current, path));
    });
  };

  const actions: TreeActions | null =
    urlOf === null
      ? null
      : {
          isWide: shownTab === undefined,
          selected: tabs.selected,
          urlOf,
          onToggle: files.toggleFolder,
          onOpenFile: (path, name) => {
            setTabs((current) => openTab(current, { path, name }));
            files.markSeen(path);
          },
          onDelete: deleteEntry,
        };

  return (
    <>
      <FileTabs
        tabs={tabs}
        onSelect={(path) => setTabs((current) => ({ ...current, selected: path }))}
        onClose={(path) => setTabs((current) => closeTab(current, path))}
      />
      {files.error !== null && (
        <p role="alert" className="bg-danger-soft px-3 py-2 break-words text-danger">
          {files.error}
        </p>
      )}
      <div className="flex min-h-0 flex-1">
        <aside
          aria-label={`${choice.name} workspace`}
          className={
            shownTab === undefined
              ? "flex min-w-0 flex-1 flex-col"
              : "flex w-[220px] shrink-0 flex-col border-r border-line"
          }
        >
          <div className="flex items-center justify-between gap-2 px-3.5 pt-3 pb-1.5">
            {switcher ?? (
              <span className="min-w-0 truncate text-[11px] font-semibold tracking-[0.06em] text-ink-soft uppercase">
                {choice.name}
              </span>
            )}
            {files.isLive && <LiveDot />}
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            {actions !== null ? (
              <WorkspaceTree tree={files.tree} actions={actions} />
            ) : (
              files.error === null && <p className="px-3 py-3 text-ink-soft">Loading…</p>
            )}
          </div>
        </aside>
        {shownTab !== undefined && urlOf !== null && (
          <FileView
            key={shownTab.path}
            workspaceName={choice.name}
            path={shownTab.path}
            entry={entryAt(files.tree, parentPath(shownTab.path), shownTab.name)}
            url={urlOf(shownTab.path)}
            onDelete={() => deleteEntry(shownTab.path)}
          />
        )}
      </div>
    </>
  );
}

function LiveDot() {
  return (
    <span className="flex shrink-0 items-center gap-1.5 text-[11px] text-ink-soft">
      <span aria-hidden className="size-1.5 rounded-full bg-accent" />
      Live
    </span>
  );
}
