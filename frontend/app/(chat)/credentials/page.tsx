"use client";

import { useCallback, useEffect, useState } from "react";

import { CredentialRow, EMPTY_DRAFT, type Draft } from "@/components/credentials/CredentialRow";
import { ApiError, canSaveCredentials, listCredentials, saveCredentials } from "@/lib/api";
import type { Credential, CredentialValues } from "@/lib/types";

const BUSY_STATUS = 409;
const RESTART_WAIT_MS = 60_000;
const RESTART_POLL_MS = 1_000;
const BUSY_QUESTION = "A reply is being written and will stop. Save and restart?";
const SAVE_BUTTON =
  "rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition disabled:opacity-40";

/** The harness's own keys and tokens: masked everywhere, changeable only on the Mac that runs it. */
export default function CredentialsPage() {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [directUrl, setDirectUrl] = useState<string | null>(null);
  const [answeringPid, setAnsweringPid] = useState<number | null>(null);
  const [canSave, setCanSave] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadCredentials = useCallback(async () => {
    try {
      const listed = await listCredentials();
      setCredentials(listed.credentials);
      setDirectUrl(listed.direct_url);
      setAnsweringPid(listed.answering_pid);
      setCanSave(await canSaveCredentials(listed.direct_url));
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not load credentials.");
    }
  }, []);

  useEffect(() => {
    void loadCredentials();
  }, [loadCredentials]);

  const toSave = valuesToSave(drafts);
  const saveChanges = async () => {
    if (directUrl === null || answeringPid === null) return;
    setNotice(null);
    try {
      if (!(await saveUnlessDeclined(directUrl, toSave))) {
        setNotice("Nothing was saved.");
        return;
      }
      setDrafts({});
      setNotice("Saved. Restarting the harness…");
      const isApplied = await hasHarnessRestarted(answeringPid);
      setNotice(isApplied ? "Saved and applied." : "Saved, but the harness has not come back yet. Check its log.");
      await loadCredentials();
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
        {canSave && (
          <button type="button" disabled={Object.keys(toSave).length === 0} onClick={() => void saveChanges()} className={`ml-auto ${SAVE_BUTTON}`}>
            Save
          </button>
        )}
      </header>

      {error && (
        <div className="border-b border-danger/30 bg-danger-soft px-6 py-2 text-sm text-danger">{error}</div>
      )}
      {notice && <div className="border-b border-line bg-accent-soft px-6 py-2 text-sm">{notice}</div>}

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        {!canSave && credentials.length > 0 && (
          <p className="mb-3 max-w-2xl text-xs text-ink-soft">
            Change credentials on the Mac that runs the harness.
          </p>
        )}
        <ul className="max-w-2xl divide-y divide-line rounded-xl border border-line bg-surface-sunken">
          {credentials.map((credential) => (
            <CredentialRow
              key={credential.path}
              credential={credential}
              canSave={canSave}
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
async function saveUnlessDeclined(directUrl: string, values: CredentialValues): Promise<boolean> {
  try {
    await saveCredentials(directUrl, values, false);
    return true;
  } catch (err: unknown) {
    if (!(err instanceof ApiError && err.status === BUSY_STATUS)) throw err;
  }
  if (!window.confirm(BUSY_QUESTION)) return false;
  await saveCredentials(directUrl, values, true);
  return true;
}

/** Whether a new harness process answers within the wait. */
async function hasHarnessRestarted(previousPid: number): Promise<boolean> {
  const deadline = Date.now() + RESTART_WAIT_MS;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, RESTART_POLL_MS));
    const answeringPid = await listCredentials().then(
      (listed) => listed.answering_pid,
      () => previousPid,
    );
    if (answeringPid !== previousPid) return true;
  }
  return false;
}

function valuesToSave(drafts: Record<string, Draft>): CredentialValues {
  return Object.fromEntries(
    Object.entries(drafts)
      .filter(([, draft]) => draft.shouldRemove || draft.value !== "")
      .map(([path, draft]) => [path, draft.shouldRemove ? null : draft.value]),
  );
}
