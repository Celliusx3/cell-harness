"use client";

import { useState, type FormEvent } from "react";

import { CredentialFields } from "@/components/credentials/CredentialFields";
import {
  credentialChange,
  credentialDraft,
  initialForm,
  type CredentialForm,
  type EditableCredential,
} from "@/components/credentials/credentialForm";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api";
import { addCredential, changeCredential } from "@/lib/credentials";
import type { Bot } from "@/lib/types";

interface CredentialDialogProps {
  directUrl: string;
  credential: EditableCredential | null;
  bots: Bot[];
  onClose: () => void;
  onSaved: () => void;
}

/** Adds a credential, or edits one with its type and name fixed; an empty key keeps the saved one. */
export function CredentialDialog({ directUrl, credential, bots, onClose, onSaved }: CredentialDialogProps) {
  const [form, setForm] = useState<CredentialForm>(() => initialForm(credential));
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      await saveForm(directUrl, credential, form);
      onSaved();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not reach the harness to save.");
      setIsSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-md">
        <form onSubmit={(event) => void handleSubmit(event)} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{credential === null ? "Add credential" : `Edit ${credential.name}`}</DialogTitle>
            <DialogDescription>
              {credential === null ? "Pick a type, then fill in its fields." : "Leave the key empty to keep the one saved."}
            </DialogDescription>
          </DialogHeader>
          <CredentialFields form={form} isEditing={credential !== null} bots={bots} onChange={setForm} />
          {error && (
            <p className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm break-words text-danger">
              {error}
            </p>
          )}
          <DialogFooter>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink-soft transition hover:bg-line hover:text-ink"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-35"
            >
              {isSaving ? "Saving…" : "Save"}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function saveForm(directUrl: string, credential: EditableCredential | null, form: CredentialForm): Promise<void> {
  return credential === null
    ? addCredential(directUrl, credentialDraft(form))
    : changeCredential(directUrl, credential.name, credentialChange(form));
}
