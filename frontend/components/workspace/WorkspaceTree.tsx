"use client";

import { ChevronRightIcon, FolderIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";

import { sizeLabel } from "@/components/computer/files";
import { DeleteConfirm } from "@/components/workspace/DeleteConfirm";
import type { Tree } from "@/components/workspace/tree";
import { childPath, type WorkspaceEntry } from "@/components/workspace/workspace";

const ROW = "flex h-7 items-center gap-1.5 rounded-md pr-2";
const INDENT_PX = 14;
const ROW_START_PX = 8;
const FILE_EXTRA_PX = 17;
const DOWNLOAD =
  "shrink-0 rounded-md border border-line px-2 py-0.5 text-xs text-ink-soft transition hover:text-ink";

/** What the tree lets the person do, and how wide it is drawn. */
export interface TreeActions {
  isWide: boolean;
  selected: string | null;
  urlOf(path: string): string;
  onToggle(folder: string): void;
  onOpenFile(path: string, name: string): void;
  onDelete(path: string): void;
}

/** The workspace as a tree: folders open in place, files open in a tab. */
export function WorkspaceTree({ tree, actions }: { tree: Tree; actions: TreeActions }) {
  const [confirming, setConfirming] = useState<string | null>(null);
  const root = tree.listings.get("");
  if (root === undefined) return <p className="px-3 py-3 text-ink-soft">Loading…</p>;
  if (root.length === 0) return <p className="px-3 py-3 text-ink-soft">This workspace is empty.</p>;
  const level = { tree, actions, confirming, onConfirm: setConfirming };
  return (
    <ul role="tree" aria-label="Workspace" className="flex flex-col px-1.5 py-0.5">
      <TreeLevel level={level} folder="" depth={0} />
    </ul>
  );
}

interface Level {
  tree: Tree;
  actions: TreeActions;
  confirming: string | null;
  onConfirm(path: string | null): void;
}

function TreeLevel({ level, folder, depth }: { level: Level; folder: string; depth: number }) {
  const entries = level.tree.listings.get(folder);
  if (entries === undefined) return <Note depth={depth}>Loading…</Note>;
  if (entries.length === 0) return <Note depth={depth}>Empty</Note>;
  return entries.map((entry) => (
    <TreeRow key={entry.name} level={level} path={childPath(folder, entry.name)} entry={entry} depth={depth} />
  ));
}

function Note({ depth, children }: { depth: number; children: string }) {
  return (
    <li className="py-1 text-xs text-ink-soft" style={{ paddingLeft: ROW_START_PX + FILE_EXTRA_PX + depth * INDENT_PX }}>
      {children}
    </li>
  );
}

interface RowProps {
  level: Level;
  path: string;
  entry: WorkspaceEntry;
  depth: number;
}

function TreeRow({ level, path, entry, depth }: RowProps) {
  const isConfirming = level.confirming === path;
  const isExpanded = entry.kind === "folder" && level.tree.expanded.has(path);
  return (
    <li role="treeitem" aria-expanded={entry.kind === "folder" ? isExpanded : undefined} aria-selected={level.actions.selected === path}>
      {entry.kind === "folder" ? (
        <FolderRow level={level} path={path} entry={entry} depth={depth} />
      ) : (
        <FileRow level={level} path={path} entry={entry} depth={depth} />
      )}
      {isConfirming && (
        <div className="my-1" style={{ marginLeft: depth * INDENT_PX }}>
          <DeleteConfirm
            name={entry.name}
            onCancel={() => level.onConfirm(null)}
            onDelete={() => {
              level.onConfirm(null);
              level.actions.onDelete(path);
            }}
          />
        </div>
      )}
      {isExpanded && (
        <ul role="group">
          <TreeLevel level={level} folder={path} depth={depth + 1} />
        </ul>
      )}
    </li>
  );
}

function FolderRow({ level, path, entry, depth }: RowProps) {
  const isExpanded = level.tree.expanded.has(path);
  return (
    <div className={`group ${ROW} hover:bg-surface-sunken`} style={{ paddingLeft: ROW_START_PX + depth * INDENT_PX }}>
      <button
        type="button"
        onClick={() => level.actions.onToggle(path)}
        className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
      >
        <ChevronRightIcon className={`size-3 shrink-0 text-ink-soft transition ${isExpanded ? "rotate-90" : ""}`} aria-hidden />
        <FolderIcon className="size-3.5 shrink-0 text-ink-soft" aria-hidden />
        <span className="min-w-0 truncate">{entry.name}</span>
      </button>
      <DeleteButton name={entry.name} isHoverOnly={!level.actions.isWide} onClick={() => level.onConfirm(path)} />
    </div>
  );
}

function FileRow({ level, path, entry, depth }: RowProps) {
  const { actions } = level;
  const isSelected = actions.selected === path;
  return (
    <div
      className={`group ${ROW} ${isSelected ? "bg-accent-soft font-medium" : "hover:bg-surface-sunken"}`}
      style={{ paddingLeft: ROW_START_PX + FILE_EXTRA_PX + depth * INDENT_PX }}
    >
      <button
        type="button"
        onClick={() => actions.onOpenFile(path, entry.name)}
        className="flex min-w-0 flex-1 items-center gap-2 text-left"
      >
        <span className="min-w-0 truncate" title={entry.name}>
          {entry.name}
        </span>
        {level.tree.fresh.has(path) && <span className="shrink-0 text-[10px] font-semibold text-accent">new</span>}
        {actions.isWide && (
          <span className="ml-auto shrink-0 text-xs text-ink-soft tabular-nums">{sizeLabel(entry.size)}</span>
        )}
      </button>
      {actions.isWide && (
        <>
          <a href={actions.urlOf(path)} download={entry.name} className={DOWNLOAD}>
            Download
          </a>
          <DeleteButton name={entry.name} isHoverOnly={false} onClick={() => level.onConfirm(path)} />
        </>
      )}
    </div>
  );
}

interface DeleteButtonProps {
  name: string;
  isHoverOnly: boolean;
  onClick: () => void;
}

function DeleteButton({ name, isHoverOnly, onClick }: DeleteButtonProps) {
  const shown = isHoverOnly ? "opacity-0 group-hover:opacity-100 focus-visible:opacity-100" : "";
  return (
    <button
      type="button"
      aria-label={`Delete ${name}`}
      onClick={onClick}
      className={`shrink-0 rounded-md p-1 text-ink-soft transition hover:bg-danger-soft hover:text-danger ${shown}`}
    >
      <Trash2Icon className="size-3.5" aria-hidden />
    </button>
  );
}
