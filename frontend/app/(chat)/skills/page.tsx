"use client";

import { useCallback, useEffect, useState } from "react";

import { SkillEditor } from "@/components/SkillEditor";
import { SkillRows } from "@/components/SkillRows";
import { ApiError, listSkills } from "@/lib/api";
import type { SkillList } from "@/lib/types";

const EMPTY: SkillList = { skills: [], problems: [] };

/** The skills on disk, and an editor for the root a person may write. */
export default function SkillsPage() {
  const [list, setList] = useState<SkillList>(EMPTY);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setList(await listSkills());
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not load skills.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">Skills</h1>
        <span className="shrink-0 text-xs text-ink-soft">
          {list.skills.length} loaded
          {list.problems.length > 0 ? ` · ${list.problems.length} not loaded` : ""}
        </span>
      </header>

      {error && (
        <div className="border-b border-danger/30 bg-danger-soft px-6 py-2 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <div className="w-80 shrink-0 overflow-y-auto border-r border-line">
          <SkillRows
            list={list}
            selected={selected}
            onSelect={setSelected}
            onNew={() => setSelected(null)}
          />
        </div>
        <div className="min-w-0 flex-1 overflow-y-auto">
          <SkillEditor
            key={selected ?? ""}
            name={selected}
            editable={selected === null || (list.skills.find((s) => s.name === selected)?.editable ?? false)}
            onSaved={(name) => {
              setSelected(name);
              void refresh();
            }}
            onDeleted={() => {
              setSelected(null);
              void refresh();
            }}
          />
        </div>
      </div>
    </>
  );
}
