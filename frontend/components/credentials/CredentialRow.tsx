import type { Credential, CredentialDetails } from "@/lib/types";

export function CredentialRow({ credential }: { credential: Credential }) {
  const purpose = purposeLabel(credential.details);
  return (
    <li className="px-3 py-2 text-sm">
      <div className="flex items-baseline gap-2">
        <span className="min-w-0 break-all font-mono text-[13px]">{credential.name}</span>
        {purpose !== null && <span className="min-w-0 break-words text-xs text-ink-soft">{purpose}</span>}
        <span className="ml-auto shrink-0 text-xs text-ink-soft">{maskLabel(credential.last_four)}</span>
      </div>
      <p className="mt-1 break-words text-xs text-ink-soft">{botsLabel(credential.bots)}</p>
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
