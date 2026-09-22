"use client";

import { Plus } from "lucide-react";

import type { SkillList } from "@/lib/types";

interface SkillRowsProps {
  list: SkillList;
  selected: string | null;
  onSelect: (name: string) => void;
  onNew: () => void;
}

/** The catalog as a list: every skill that loaded, then everything that did not. */
export function SkillRows({ list, selected, onSelect, onNew }: SkillRowsProps) {
  return (
    <div className="px-2 py-3">
      <button
        type="button"
        onClick={onNew}
        className={`mb-2 flex w-full items-center gap-1.5 rounded-md px-2 py-2 text-sm transition ${
          selected === null ? "bg-accent-soft font-medium text-ink" : "text-ink-soft hover:bg-line hover:text-ink"
        }`}
      >
        <Plus size={16} /> New skill
      </button>

      {list.skills.length === 0 ? (
        <p className="px-2 py-3 text-xs text-ink-soft">No skills on disk.</p>
      ) : (
        <ul className="space-y-0.5">
          {list.skills.map((skill) => (
            <li key={skill.dir}>
              <button
                type="button"
                onClick={() => onSelect(skill.name)}
                className={`block w-full rounded-md px-2 py-2 text-left transition ${
                  skill.name === selected ? "bg-accent-soft" : "hover:bg-line"
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-sm">{skill.name}</span>
                  {!skill.editable && <Chip>read-only</Chip>}
                  {!skill.model_invocable && <Chip>no model</Chip>}
                  {!skill.user_invocable && <Chip>no /name</Chip>}
                </div>
                <p className="mt-0.5 line-clamp-2 text-xs text-ink-soft">{skill.description}</p>
              </button>
            </li>
          ))}
        </ul>
      )}

      {list.problems.length > 0 && (
        <div className="mt-4">
          <p className="mb-1 px-2 text-[11px] font-medium uppercase tracking-wide text-ink-soft">
            Not loaded
          </p>
          <ul className="space-y-1">
            {list.problems.map((problem) => (
              <li key={problem.path} className="px-2 text-xs">
                <p className="break-all font-mono text-ink-soft">{problem.path}</p>
                <p className="text-danger">{problem.problem}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-md border border-line bg-surface px-1.5 py-0.5 text-[10px] text-ink-soft">
      {children}
    </span>
  );
}
