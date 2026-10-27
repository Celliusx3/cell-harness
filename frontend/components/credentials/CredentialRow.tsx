import type { Credential } from "@/lib/types";

const INPUT =
  "min-w-0 flex-1 rounded-md border border-line bg-surface px-2 py-1 font-mono text-xs outline-none focus:border-accent";
const TOGGLE_BUTTON = "shrink-0 rounded-md border border-line px-2 py-1 text-xs transition hover:bg-line";

export interface Draft {
  readonly value: string;
  readonly shouldRemove: boolean;
}

export const EMPTY_DRAFT: Draft = { value: "", shouldRemove: false };

interface CredentialRowProps {
  credential: Credential;
  canSave: boolean;
  draft: Draft;
  onChange: (draft: Draft) => void;
}

export function CredentialRow({ credential, canSave, draft, onChange }: CredentialRowProps) {
  const isSettable = canSave && credential.env_variable === null;
  return (
    <li className="px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <span className="rounded-md border border-line bg-surface px-1.5 py-0.5 font-mono text-[11px]">
          {credential.path}
        </span>
        <span className="text-xs text-ink-soft">{stateLabel(credential, draft)}</span>
      </div>
      <p className="mt-1 break-words text-xs text-ink-soft">{credential.description}</p>
      {isSettable && (
        <div className="mt-2 flex items-center gap-2">
          <input
            type="password"
            autoComplete="off"
            aria-label={`New value for ${credential.path}`}
            placeholder={credential.is_set ? "Paste a new key to replace it" : "Paste the key"}
            value={draft.value}
            disabled={draft.shouldRemove}
            onChange={(event) => onChange({ value: event.target.value, shouldRemove: false })}
            className={INPUT}
          />
          {credential.is_set && !credential.is_required && (
            <button
              type="button"
              onClick={() => onChange({ value: "", shouldRemove: !draft.shouldRemove })}
              className={TOGGLE_BUTTON}
            >
              {draft.shouldRemove ? "Keep" : "Remove"}
            </button>
          )}
        </div>
      )}
    </li>
  );
}

function stateLabel(credential: Credential, draft: Draft): string {
  if (draft.shouldRemove) return "will be removed";
  if (draft.value !== "") return "will be replaced";
  if (credential.env_variable !== null) return `set by ${credential.env_variable}`;
  if (!credential.is_set) return "not set";
  return credential.last_four === null ? "saved" : `saved, ends in …${credential.last_four}`;
}
