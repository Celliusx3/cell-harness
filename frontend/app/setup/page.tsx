"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { SetupColumn } from "@/components/setup/SetupColumn";
import { SetupForm } from "@/components/setup/SetupForm";
import { ApiError } from "@/lib/api";
import { canSaveCredentials, hasModelCredential, listCredentials, type CredentialList } from "@/lib/credentials";

type SetupState =
  | { kind: "loading" }
  | { kind: "failed"; message: string }
  | { kind: "alreadySetUp" }
  | { kind: "cannotSave" }
  | { kind: "canSave"; list: CredentialList };

/** Asks for the API key Assistant answers with, on the Mac that runs the harness and only before a model is saved. */
export default function SetupPage() {
  const router = useRouter();
  const [state, setState] = useState<SetupState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    readSetupState()
      .then((next) => {
        if (cancelled) return;
        setState(next);
        if (next.kind === "alreadySetUp") router.replace("/");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({ kind: "failed", message: err instanceof ApiError ? err.message : "Could not load the setup." });
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (state.kind === "alreadySetUp") return null;
  return (
    <SetupColumn>
      {state.kind === "loading" && <p className="text-sm text-ink-soft">Loading…</p>}
      {state.kind === "failed" && <p className="text-sm text-danger">{state.message}</p>}
      {state.kind === "cannotSave" && (
        <h1 className="text-center font-display text-4xl font-semibold tracking-tight text-balance">
          Finish setup on the Mac that runs Cell Harness
        </h1>
      )}
      {state.kind === "canSave" && (
        <SetupForm directUrl={state.list.direct_url} />
      )}
    </SetupColumn>
  );
}

async function readSetupState(): Promise<SetupState> {
  const list = await listCredentials();
  if (hasModelCredential(list.credentials)) return { kind: "alreadySetUp" };
  return (await canSaveCredentials(list.direct_url)) ? { kind: "canSave", list } : { kind: "cannotSave" };
}
