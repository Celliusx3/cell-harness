"use client";

import { useState, type FormEvent } from "react";

import { Errors, ServerFields } from "@/components/mcp/ServerFields";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api";
import {
  fieldErrorsFrom,
  initialServerForm,
  serverChange,
  serverDraft,
  type FieldErrors,
  type ServerForm,
} from "@/lib/mcpServerForm";
import { addMcpServer, changeMcpServer, FieldsRefused, type McpServer } from "@/lib/mcpServers";

interface ServerDialogProps {
  directUrl: string;
  server: McpServer | null;
  onClose: () => void;
  onSaved: () => void;
}

/** Adds a server, or edits one with its name fixed; it starts or restarts as soon as it is saved. */
export function ServerDialog({ directUrl, server, onClose, onSaved }: ServerDialogProps) {
  const [form, setForm] = useState<ServerForm>(() => initialServerForm(server));
  const [isSaving, setIsSaving] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setErrors({});
    const refused = await sendForm(directUrl, server, form);
    if (refused === null) {
      onSaved();
      return;
    }
    setErrors(refused);
    setIsSaving(false);
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-md">
        <form onSubmit={(event) => void handleSubmit(event)} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{server === null ? "Add server" : `Edit ${server.id}`}</DialogTitle>
            <DialogDescription>
              {server === null
                ? "A program on this Mac that gives the bots tools. It starts when you save."
                : "It restarts with the changes when you save."}
            </DialogDescription>
          </DialogHeader>
          <ServerFields form={form} isEditing={server !== null} errors={errors} onChange={setForm} />
          {(errors.form ?? []).length > 0 && (
            <div className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
              <Errors errors={errors} field="form" />
            </div>
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
              className="rounded-lg bg-action px-3 py-1 text-xs font-medium text-on-action transition hover:opacity-90 disabled:opacity-35"
            >
              {isSaving ? "Saving…" : "Save"}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Null once the harness saved it; else the errors that kept it, from the form or from the harness. */
async function sendForm(directUrl: string, server: McpServer | null, form: ServerForm): Promise<FieldErrors | null> {
  try {
    if (server === null) {
      const draft = serverDraft(form);
      if (!draft.ok) return draft.errors;
      await addMcpServer(directUrl, draft.request);
    } else {
      const change = serverChange(form);
      if (!change.ok) return change.errors;
      await changeMcpServer(directUrl, server.id, change.request);
    }
    return null;
  } catch (err: unknown) {
    if (err instanceof FieldsRefused) return fieldErrorsFrom(err.fields);
    return { form: [err instanceof ApiError ? err.message : "Could not reach the harness to save."] };
  }
}
