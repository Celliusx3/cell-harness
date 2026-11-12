"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api";
import { listCredentials, modelOptions, type ModelOption } from "@/lib/credentials";

type ModelOptions =
  | { kind: "loading" }
  | { kind: "loaded"; options: ModelOption[] }
  | { kind: "failed"; message: string };

/** The LLM credentials a bot's model is picked from, read once. */
export function useModelOptions(): ModelOptions {
  const [options, setOptions] = useState<ModelOptions>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    listCredentials()
      .then((list) => {
        if (!cancelled) setOptions({ kind: "loaded", options: modelOptions(list.credentials) });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setOptions({ kind: "failed", message: err instanceof ApiError ? err.message : "Could not load the models." });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return options;
}
