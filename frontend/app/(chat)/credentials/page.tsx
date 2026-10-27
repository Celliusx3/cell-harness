"use client";

import { useCallback, useEffect, useState } from "react";

import { CredentialRow } from "@/components/credentials/CredentialRow";
import { ApiError, listCredentials } from "@/lib/api";
import type { Credential, CredentialDetails } from "@/lib/types";

const KIND_HEADINGS: { kind: CredentialDetails["kind"]; heading: string }[] = [
  { kind: "llm", heading: "LLM" },
  { kind: "telegram", heading: "Telegram" },
  { kind: "discord", heading: "Discord" },
  { kind: "custom", heading: "Custom" },
];

/** Every credential in the keyring, grouped by kind, each with its bots and its last four characters at most. */
export default function CredentialsPage() {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadCredentials = useCallback(async () => {
    try {
      setCredentials((await listCredentials()).credentials);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not load credentials.");
    }
  }, []);

  useEffect(() => {
    void loadCredentials();
  }, [loadCredentials]);

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">Credentials</h1>
        <span className="shrink-0 text-xs text-ink-soft">{credentials.length} saved</span>
      </header>

      {error && (
        <div className="border-b border-danger/30 bg-danger-soft px-6 py-2 text-sm text-danger">{error}</div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        {credentials.length === 0 ? (
          <p className="text-sm text-ink-soft">No credentials yet.</p>
        ) : (
          <div className="max-w-2xl space-y-6">
            {KIND_HEADINGS.map(({ kind, heading }) => (
              <CredentialGroup
                key={kind}
                heading={heading}
                credentials={credentials.filter((credential) => credential.details.kind === kind)}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function CredentialGroup({ heading, credentials }: { heading: string; credentials: Credential[] }) {
  if (credentials.length === 0) return null;
  return (
    <section>
      <h2 className="pb-2 text-xs font-medium text-ink-soft">{heading}</h2>
      <ul className="divide-y divide-line rounded-xl border border-line bg-surface-sunken">
        {credentials.map((credential) => (
          <CredentialRow key={credential.name} credential={credential} />
        ))}
      </ul>
    </section>
  );
}
