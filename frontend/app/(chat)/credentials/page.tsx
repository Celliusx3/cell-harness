"use client";

import { useCallback, useEffect, useState } from "react";

import { CredentialRow } from "@/components/credentials/CredentialRow";
import { ApiError, listCredentials } from "@/lib/api";
import type { Credential } from "@/lib/types";

/** The harness's own keys and tokens, each shown only by whether it is saved and its last four characters. */
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
        <span className="shrink-0 text-xs text-ink-soft">
          {credentials.filter((credential) => credential.is_set).length} of {credentials.length} saved
        </span>
      </header>

      {error && (
        <div className="border-b border-danger/30 bg-danger-soft px-6 py-2 text-sm text-danger">{error}</div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        <ul className="max-w-2xl divide-y divide-line rounded-xl border border-line bg-surface-sunken">
          {credentials.map((credential) => (
            <CredentialRow key={credential.path} credential={credential} />
          ))}
        </ul>
      </div>
    </>
  );
}
