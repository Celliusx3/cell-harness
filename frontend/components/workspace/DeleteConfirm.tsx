"use client";

import { deleteQuestion } from "@/components/workspace/workspace";

interface DeleteConfirmProps {
  name: string;
  onCancel: () => void;
  onDelete: () => void;
}

/** The question asked in place before `name` is deleted, with Cancel and Delete. */
export function DeleteConfirm({ name, onCancel, onDelete }: DeleteConfirmProps) {
  return (
    <div role="alertdialog" aria-label={`Delete ${name}`} className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2">
      <p className="break-words text-danger">{deleteQuestion(name)}</p>
      <div className="mt-2 flex justify-end gap-2">
        <button
          type="button"
          autoFocus
          onClick={onCancel}
          className="h-7 rounded-md border border-line bg-surface-raised px-3 text-xs font-medium text-ink transition hover:bg-surface-sunken"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="h-7 rounded-md bg-danger px-3 text-xs font-medium text-surface-raised transition hover:opacity-90"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
