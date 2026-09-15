"use client";

import { useEffect, useState } from "react";

import { ApiError, deleteSkill, getSkill, putSkill } from "@/lib/api";

interface SkillEditorProps {
  /** The skill open for editing, or `null` for a new one. */
  name: string | null;
  /** Whether saving is allowed — false for a skill in a read-only root. */
  editable: boolean;
  onSaved: (name: string) => void;
  onDeleted: () => void;
}

const TEMPLATE = `---
name: my-skill
description: What it does, and when to use it.
---

# My skill

Instructions the model follows once this is loaded.
`;

/**
 * One `SKILL.md`, whole.
 *
 * Paste a public skill and save: the backend validates it the way the catalog
 * would (and stricter — a mismatched frontmatter name is refused, not noted)
 * and writes it to the editable root. A read-only skill can be read here but
 * not saved over; its path says where it lives.
 */
export function SkillEditor({ name, editable, onSaved, onDeleted }: SkillEditorProps) {
  const [draftName, setDraftName] = useState(name ?? "");
  const [text, setText] = useState(name === null ? TEMPLATE : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (name === null) return;
    let cancelled = false;
    getSkill(name)
      .then((file) => {
        if (!cancelled) setText(file.text);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load skill.");
      });
    return () => {
      cancelled = true;
    };
  }, [name]);

  const target = (name ?? draftName).trim();

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await putSkill(target, text);
      onSaved(target);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not save skill.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (name === null || !window.confirm(`Delete the skill "${name}" and its directory?`)) return;
    setBusy(true);
    setError(null);
    try {
      await deleteSkill(name);
      onDeleted();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not delete skill.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex h-full w-full max-w-3xl flex-col gap-3 px-6 py-5">
      <div className="flex items-center gap-2">
        <label className="text-xs text-ink-soft" htmlFor="skill-name">
          Name
        </label>
        <input
          id="skill-name"
          value={name ?? draftName}
          onChange={(event) => setDraftName(event.target.value)}
          disabled={name !== null}
          placeholder="my-skill"
          spellCheck={false}
          className="min-w-0 flex-1 rounded-lg border border-line bg-surface-sunken px-2.5 py-1.5 font-mono text-sm outline-none focus:border-accent disabled:opacity-60"
        />
        {name !== null && editable && (
          <button
            type="button"
            onClick={remove}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-danger/40 bg-surface px-2.5 py-1 text-xs font-medium text-danger hover:bg-danger-soft disabled:opacity-35"
          >
            Delete
          </button>
        )}
        <button
          type="button"
          onClick={save}
          disabled={busy || !editable || target === "" || text.trim() === ""}
          className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-35"
        >
          Save
        </button>
      </div>

      {!editable && (
        <p className="text-xs text-ink-soft">
          Read-only: this skill lives outside the editable root. Edit the file directly.
        </p>
      )}

      {error && (
        <p className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        readOnly={!editable}
        spellCheck={false}
        aria-label="SKILL.md"
        className="min-h-0 flex-1 resize-none rounded-xl border border-line bg-surface-sunken p-3 font-mono text-xs outline-none focus:border-accent"
      />
    </div>
  );
}
