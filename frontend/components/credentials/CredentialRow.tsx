import type { Credential, CredentialDetails } from "@/lib/credentials";

const ROW_BUTTON =
  "shrink-0 rounded-md border border-line bg-surface px-2 py-0.5 text-xs text-ink-soft transition hover:bg-line hover:text-ink";

interface CredentialRowProps {
  credential: Credential;
  onEdit: (() => void) | null;
  onRemove: (() => void) | null;
}

export function CredentialRow({ credential, onEdit, onRemove }: CredentialRowProps) {
  const purpose = purposeLabel(credential.details);
  return (
    <li className="px-3 py-2 text-sm">
      <div className="flex items-baseline gap-2">
        <span className="min-w-0 break-all font-mono text-[13px]">{credential.name}</span>
        {purpose !== null && <span className="min-w-0 break-words text-xs text-ink-soft">{purpose}</span>}
        <span className="ml-auto shrink-0 text-xs text-ink-soft">{maskLabel(credential.last_four)}</span>
      </div>
      <div className="mt-1 flex items-center gap-2">
        <p className="min-w-0 flex-1 break-words text-xs text-ink-soft">{botsLabel(credential.bots)}</p>
        {onEdit !== null && (
          <button type="button" onClick={onEdit} className={ROW_BUTTON}>
            Edit
          </button>
        )}
        {onRemove !== null && (
          <button type="button" onClick={onRemove} className={ROW_BUTTON}>
            Remove
          </button>
        )}
      </div>
    </li>
  );
}

function purposeLabel(details: CredentialDetails): string | null {
  switch (details.kind) {
    case "custom":
      return new URL(details.destination.origin).host;
    case "llm":
      return `${details.model} at ${new URL(details.base_url).host}`;
    case "telegram":
    case "discord":
      return null;
    default: {
      const _exhaustive: never = details;
      return _exhaustive;
    }
  }
}

function botsLabel(bots: Credential["bots"]): string {
  return bots.length === 0 ? "no bots" : bots.map((bot) => bot.name).join(", ");
}

function maskLabel(lastFour: string | null): string {
  return lastFour === null ? "saved" : `ends in …${lastFour}`;
}
