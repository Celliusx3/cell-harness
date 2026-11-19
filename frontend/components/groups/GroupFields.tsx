"use client";

import type { Bot } from "@/lib/types";

const MIN_MEMBERS = 2;
const MAX_MEMBERS = 6;

interface GroupFieldsProps {
  name: string;
  onName: (name: string) => void;
  bots: Bot[];
  picked: string[];
  onPicked: (picked: string[]) => void;
}

/** Whether a group of this name and these members can be saved. */
export function groupIsReady(name: string, picked: string[]): boolean {
  return name.trim() !== "" && picked.length >= MIN_MEMBERS && picked.length <= MAX_MEMBERS;
}

/** A group's name and its two to six members, numbered in the order they were picked. */
export function GroupFields({ name, onName, bots, picked, onPicked }: GroupFieldsProps) {
  const toggle = (id: string) =>
    onPicked(picked.includes(id) ? picked.filter((each) => each !== id) : [...picked, id]);

  return (
    <>
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-ink-soft" htmlFor="group-name">
          Name
        </label>
        <input
          id="group-name"
          value={name}
          autoFocus
          onChange={(event) => onName(event.target.value)}
          className="rounded-lg border border-line bg-surface-sunken px-2.5 py-1.5 text-sm outline-none focus:border-accent"
        />
      </div>

      <fieldset className="flex flex-col gap-1.5">
        <legend className="pb-1.5 text-xs text-ink-soft">
          Members: pick {MIN_MEMBERS} to {MAX_MEMBERS}. They take turns in the order you pick them.
        </legend>
        {bots.map((bot) => {
          const at = picked.indexOf(bot.id);
          return (
            <label
              key={bot.id}
              className="flex items-center gap-2 rounded-lg border border-line px-2.5 py-1.5 text-sm"
            >
              <input type="checkbox" checked={at >= 0} onChange={() => toggle(bot.id)} />
              <span className="min-w-0 flex-1 truncate">{bot.name}</span>
              {at >= 0 && <span className="text-xs text-ink-soft">{at + 1}</span>}
            </label>
          );
        })}
      </fieldset>
    </>
  );
}
