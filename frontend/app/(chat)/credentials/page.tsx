"use client";

import { useCallback, useEffect, useState } from "react";

import { CredentialRow, EMPTY_DRAFT, type Draft } from "@/components/credentials/CredentialRow";
import { ApiError, canSaveCredentials, listCredentials, saveCredentials } from "@/lib/api";
import type { Credential, CredentialValues } from "@/lib/types";

const BUSY = 409;
const BUSY_QUESTION = "A reply is being written and will stop. Save and restart?";
const SAVE =
  "rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition disabled:opacity-40";

/** The harness's own keys and tokens: masked everywhere, changeable only on the Mac that runs it. */
export default function CredentialsPage() {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [directUrl, setDirectUrl] = useState<string | null>(null);
  const [editable, setEditable] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const listed = await listCredentials();
      setCredentials(listed.credentials);
      setDirectUrl(listed.direct_url);
      setEditable(await canSaveCredentials(listed.direct_url));
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not load credentials.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const values = changedValues(drafts);
  const save = async () => {
    if (directUrl === null) return;
    setNotice(null);
    try {
      if (!(await saveAsking(directUrl, values))) {
        setNotice("Nothing was saved.");
        return;
      }
      setDrafts({});
      setNotice("Saved. The harness restarts to use the new keys.");
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not save the credentials.");
    }
  };

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">Credentials</h1>
        <span className="shrink-0 text-xs text-ink-soft">
          {credentials.filter((credential) => credential.is_set).length} of {credentials.length} saved
        </span>
        {editable && (
          <button type="button" disabled={Object.keys(values).length === 0} onClick={() => void save()} className={`ml-auto ${SAVE}`}>
            Save
          </button>
        )}
      </header>

      {error && (
        <div className="border-b border-danger/30 bg-danger-soft px-6 py-2 text-sm text-danger">{error}</div>
      )}
      {notice && <div className="border-b border-line bg-accent-soft px-6 py-2 text-sm">{notice}</div>}

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        {!editable && credentials.length > 0 && (
          <p className="mb-3 max-w-2xl text-xs text-ink-soft">
            Change credentials on the Mac that runs the harness.
          </p>
        )}
        <ul className="max-w-2xl divide-y divide-line rounded-xl border border-line bg-surface-sunken">
          {credentials.map((credential) => (
            <CredentialRow
              key={credential.path}
              credential={credential}
              editable={editable}
              draft={drafts[credential.path] ?? EMPTY_DRAFT}
              onChange={(draft) => setDrafts((current) => ({ ...current, [credential.path]: draft }))}
            />
          ))}
        </ul>
      </div>
    </>
  );
}

/** Whether the keys were saved; if a reply is being written, only after the person says yes. */
async function saveAsking(directUrl: string, values: CredentialValues): Promise<boolean> {
  try {
    await saveCredentials(directUrl, values, false);
    return true;
  } catch (err: unknown) {
    if (!(err instanceof ApiError && err.status === BUSY)) throw err;
  }
  if (!window.confirm(BUSY_QUESTION)) return false;
  await saveCredentials(directUrl, values, true);
  return true;
}

function changedValues(drafts: Record<string, Draft>): CredentialValues {
  return Object.fromEntries(
    Object.entries(drafts)
      .filter(([, draft]) => draft.remove || draft.value !== "")
      .map(([path, draft]) => [path, draft.remove ? null : draft.value]),
  );
}
