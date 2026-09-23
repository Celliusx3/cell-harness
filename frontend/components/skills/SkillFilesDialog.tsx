"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { fileTree, type TreeNode } from "@/components/skills/fileTree";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError, getSkillFile } from "@/lib/api";

interface SkillFilesDialogProps {
  name: string;
  files: string[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** What the skill bundles beside its `SKILL.md`: the tree, and one file at a time. */
export function SkillFilesDialog({ name, files, open, onOpenChange }: SkillFilesDialogProps) {
  const tree = useMemo(() => fileTree(files), [files]);
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set<string>());
  const [selected, setSelected] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSelected(null);
  }, [name, open]);

  useEffect(() => {
    setText("");
    setError(null);
    if (selected === null) return;
    let cancelled = false;
    getSkillFile(name, selected)
      .then((file) => {
        if (!cancelled) setText(file.text);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load file.");
      });
    return () => {
      cancelled = true;
    };
  }, [name, selected]);

  function toggle(path: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="h-[32rem] grid-rows-[auto_minmax(0,1fr)] sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="font-mono">{name}</DialogTitle>
          <DialogDescription>The files this skill bundles beside its SKILL.md.</DialogDescription>
        </DialogHeader>
        <div className="grid min-h-0 grid-cols-[14rem_minmax(0,1fr)] gap-3">
          <div className="min-h-0 overflow-auto rounded-xl border border-line bg-surface-sunken py-2">
            <TreeRows
              nodes={tree}
              depth={0}
              collapsed={collapsed}
              selected={selected}
              onToggle={toggle}
              onSelect={setSelected}
            />
          </div>
          <div className="flex min-h-0 flex-col gap-2">
            {error && (
              <p className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}
            {selected === null ? (
              <p className="flex min-h-0 flex-1 items-center justify-center rounded-xl border border-line bg-surface-sunken p-3 text-xs text-ink-soft">
                Pick a file to read it.
              </p>
            ) : (
              <textarea
                value={text}
                readOnly
                spellCheck={false}
                aria-label={selected}
                className="min-h-0 flex-1 resize-none rounded-xl border border-line bg-surface-sunken p-3 font-mono text-xs outline-none"
              />
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface TreeRowsProps {
  nodes: TreeNode[];
  depth: number;
  collapsed: ReadonlySet<string>;
  selected: string | null;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
}

function TreeRows({ nodes, depth, collapsed, selected, onToggle, onSelect }: TreeRowsProps) {
  return (
    <>
      {nodes.map((node) =>
        node.kind === "folder" ? (
          <div key={node.path}>
            <Row
              depth={depth}
              selected={false}
              onClick={() => onToggle(node.path)}
              icon={
                collapsed.has(node.path) ? (
                  <ChevronRight size={12} className="shrink-0" />
                ) : (
                  <ChevronDown size={12} className="shrink-0" />
                )
              }
              name={node.name}
            />
            {!collapsed.has(node.path) && (
              <TreeRows
                nodes={node.children}
                depth={depth + 1}
                collapsed={collapsed}
                selected={selected}
                onToggle={onToggle}
                onSelect={onSelect}
              />
            )}
          </div>
        ) : (
          <Row
            key={node.path}
            depth={depth}
            selected={node.path === selected}
            onClick={() => onSelect(node.path)}
            icon={null}
            name={node.name}
          />
        ),
      )}
    </>
  );
}

interface RowProps {
  depth: number;
  selected: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  name: string;
}

function Row({ depth, selected, onClick, icon, name }: RowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{ paddingLeft: `${0.5 + depth * 0.75}rem` }}
      className={`flex w-full min-w-0 items-center gap-1 py-1 pr-2 text-left font-mono text-xs transition ${
        selected ? "bg-accent-soft text-ink" : "text-ink-soft hover:bg-line hover:text-ink"
      }`}
    >
      {icon ?? <span className="w-3 shrink-0" />}
      <span className="truncate">{name}</span>
    </button>
  );
}
