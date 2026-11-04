"use client";

import { useEffect, useState } from "react";

import { SetupForm } from "@/components/setup/SetupForm";
import { ApiError } from "@/lib/api";
import { listCredentials, type CredentialList } from "@/lib/credentials";

/** Asks for the API key that becomes the Default model, at the endpoint and model the harness ships with. */
export default function SetupPage() {
  const [listed, setListed] = useState<CredentialList | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listCredentials()
      .then((list) => {
        if (!cancelled) setListed(list);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load the setup.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="flex min-w-0 flex-1 flex-col overflow-y-auto px-4 py-10">
      <div className="m-auto w-full max-w-sm">
        {error !== null ? (
          <p className="text-sm text-danger">{error}</p>
        ) : listed === null ? (
          <p className="text-sm text-ink-soft">Loading…</p>
        ) : (
          <SetupForm shippedModel={listed.shipped_model} directUrl={listed.direct_url} />
        )}
      </div>
    </main>
  );
}
