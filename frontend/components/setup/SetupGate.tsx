"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { SetupColumn } from "@/components/setup/SetupColumn";
import { ApiError } from "@/lib/api";
import { hasDefaultModel, listCredentials } from "@/lib/credentials";

type Gate = { kind: "closed" } | { kind: "open" } | { kind: "failed"; message: string };

/** Shows the chat once the keyring holds the Default model, and sends the page to setup while it holds none. */
export function SetupGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [gate, setGate] = useState<Gate>({ kind: "closed" });

  useEffect(() => {
    let cancelled = false;
    listCredentials()
      .then((list) => {
        if (cancelled) return;
        if (hasDefaultModel(list.credentials)) setGate({ kind: "open" });
        else router.replace("/setup");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setGate({ kind: "failed", message: err instanceof ApiError ? err.message : "Could not reach the harness." });
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (gate.kind === "failed") {
    return (
      <SetupColumn>
        <p className="text-sm text-danger">{gate.message}</p>
      </SetupColumn>
    );
  }
  return gate.kind === "open" ? <>{children}</> : null;
}
