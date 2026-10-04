"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, ASSISTANT_ID, listBots } from "@/lib/api";

/** Opens Assistant's chat once the bot list has made sure it exists. */
export default function HomePage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listBots()
      .then(() => {
        if (!cancelled) router.replace(`/c/${ASSISTANT_ID}`);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load bots.");
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  return error === null ? (
    <p className="px-6 py-6 text-sm text-ink-soft">Loading…</p>
  ) : (
    <p className="px-6 py-6 text-sm text-danger">{error}</p>
  );
}
