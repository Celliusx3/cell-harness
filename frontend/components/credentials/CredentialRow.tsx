import type { Credential } from "@/lib/types";

export function CredentialRow({ credential }: { credential: Credential }) {
  return (
    <li className="px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <span className="rounded-md border border-line bg-surface px-1.5 py-0.5 font-mono text-[11px]">
          {credential.path}
        </span>
        <span className="text-xs text-ink-soft">{stateLabel(credential)}</span>
      </div>
      <p className="mt-1 break-words text-xs text-ink-soft">{credential.description}</p>
    </li>
  );
}

function stateLabel(credential: Credential): string {
  if (credential.env_variable !== null) return `set by ${credential.env_variable}`;
  if (!credential.is_set) return "not set";
  return credential.last_four === null ? "saved" : `saved, ends in …${credential.last_four}`;
}
