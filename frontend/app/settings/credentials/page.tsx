"use client";

import { useCallback, useEffect, useState } from "react";

import { CapabilityList } from "@/components/credentials/CapabilityList";
import { CredentialDialog } from "@/components/credentials/CredentialDialog";
import { CredentialRow } from "@/components/credentials/CredentialRow";
import { addableKinds, isChatPlatform } from "@/components/credentials/credentialForm";
import { ApiError, listBots, listServers } from "@/lib/api";
import { capabilityLabel, isStarting, openCapabilityKeys } from "@/lib/capabilityKeys";
import {
  canSaveCredentials,
  listCredentials,
  removeCredential,
  type Credential,
  type CredentialDetails,
} from "@/lib/credentials";
import type { Bot, KeyedServer } from "@/lib/types";

const KIND_HEADINGS: { kind: CredentialDetails["kind"]; heading: string }[] = [
  { kind: "llm", heading: "LLM" },
  { kind: "telegram", heading: "Telegram" },
  { kind: "discord", heading: "Discord" },
  { kind: "custom", heading: "Custom" },
  { kind: "capability", heading: "Capability keys" },
];

const STARTING_POLL_MS = 2000;

/** Whether the dialog is shown, and for a new credential or which one. */
type DialogState = { isOpen: false } | { isOpen: true; credential: Credential | null };

const CLOSED: DialogState = { isOpen: false };

/** Every credential in the keyring, grouped by kind; added, edited and removed only on the Mac that runs the harness. */
export default function CredentialsPage() {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [bots, setBots] = useState<Bot[]>([]);
  const [keyed, setKeyed] = useState<KeyedServer[]>([]);
  const [directUrl, setDirectUrl] = useState<string | null>(null);
  const [canSave, setCanSave] = useState<boolean | null>(null);
  const [dialog, setDialog] = useState<DialogState>(CLOSED);
  const [error, setError] = useState<string | null>(null);

  const loadCredentials = useCallback(async () => {
    try {
      const [listed, active, servers] = await Promise.all([listCredentials(), listBots(), listServers()]);
      setCredentials(listed.credentials);
      setDirectUrl(listed.direct_url);
      setBots(active);
      setKeyed(servers.keyed);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not load credentials.");
    }
  }, []);

  useEffect(() => {
    void loadCredentials();
  }, [loadCredentials]);

  useEffect(() => {
    if (!isStarting(keyed)) return;
    const timer = window.setTimeout(() => void loadCredentials(), STARTING_POLL_MS);
    return () => window.clearTimeout(timer);
  }, [keyed, loadCredentials]);

  useEffect(() => {
    if (directUrl === null) return;
    let cancelled = false;
    void canSaveCredentials(directUrl).then((can) => {
      if (!cancelled) setCanSave(can);
    });
    return () => {
      cancelled = true;
    };
  }, [directUrl]);

  async function handleRemove(credential: Credential) {
    if (directUrl === null || !window.confirm(removalQuestion(credential))) return;
    try {
      await removeCredential(directUrl, credential.name);
      await loadCredentials();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not reach the harness to remove it.");
    }
  }

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">Credentials</h1>
        <span className="shrink-0 text-xs text-ink-soft">{credentials.length} saved</span>
        {canSave === true && (
          <button
            type="button"
            onClick={() => setDialog({ isOpen: true, credential: null })}
            className="ml-auto rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90"
          >
            Add credential
          </button>
        )}
      </header>

      {error && (
        <div className="border-b border-danger/30 bg-danger-soft px-6 py-2 text-sm text-danger">{error}</div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        {canSave === false && (
          <p className="mb-3 max-w-2xl text-xs text-ink-soft">Change credentials on the Mac that runs the harness.</p>
        )}
        {credentials.length === 0 ? (
          <p className="mb-6 text-sm text-ink-soft">No credentials yet.</p>
        ) : (
          <div className="mb-6 max-w-2xl space-y-6">
            {KIND_HEADINGS.map(({ kind, heading }) => (
              <CredentialGroup
                key={kind}
                heading={heading}
                credentials={credentials.filter((credential) => credential.details.kind === kind)}
                onEdit={canSave === true ? (credential) => setDialog({ isOpen: true, credential }) : null}
                onRemove={canSave === true ? (credential) => void handleRemove(credential) : null}
              />
            ))}
          </div>
        )}
        <div className="max-w-2xl">
          <CapabilityList keyed={keyed} />
        </div>
      </div>

      {dialog.isOpen && directUrl !== null && (
        <CredentialDialog
          directUrl={directUrl}
          credential={dialog.credential}
          kinds={addableKinds(credentials, openCapabilityKeys(keyed, credentials, null).length > 0)}
          bots={bots}
          capabilityKeys={openCapabilityKeys(keyed, credentials, dialog.credential?.name ?? null)}
          onClose={() => setDialog(CLOSED)}
          onSaved={() => {
            setDialog(CLOSED);
            void loadCredentials();
          }}
        />
      )}
    </>
  );
}

interface CredentialGroupProps {
  heading: string;
  credentials: Credential[];
  onEdit: ((credential: Credential) => void) | null;
  onRemove: ((credential: Credential) => void) | null;
}

function CredentialGroup({ heading, credentials, onEdit, onRemove }: CredentialGroupProps) {
  if (credentials.length === 0) return null;
  return (
    <section>
      <h2 className="pb-2 text-xs font-medium text-ink-soft">{heading}</h2>
      <ul className="divide-y divide-line rounded-xl border border-line bg-surface-sunken">
        {credentials.map((credential) => (
          <CredentialRow
            key={credential.name}
            credential={credential}
            onEdit={onEdit !== null ? () => onEdit(credential) : null}
            onRemove={onRemove !== null && !credential.is_default_model ? () => onRemove(credential) : null}
          />
        ))}
      </ul>
    </section>
  );
}

function removalQuestion(credential: Credential): string {
  const details = credential.details;
  if (details.kind === "capability") return `Remove ${credential.name}? ${capabilityLabel(details.server)} turns off.`;
  return isChatPlatform(details.kind)
    ? `Remove ${credential.name}? Its bot stops answering.`
    : `Remove ${credential.name}? The bots it serves lose it.`;
}
