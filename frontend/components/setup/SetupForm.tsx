"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Field, INPUT_CLASSES } from "@/components/credentials/CredentialFields";
import { ApiError, ASSISTANT_ID } from "@/lib/api";
import { addCredential, type ModelDetails } from "@/lib/credentials";

const SETUP_MODEL_CREDENTIAL = "first_model";

interface SetupFormProps {
  shippedModel: ModelDetails;
  directUrl: string;
}

/** The API key saved as Assistant's model, at the endpoint and model shown, which start as the shipped ones. */
export function SetupForm({ shippedModel, directUrl }: SetupFormProps) {
  const router = useRouter();
  const [apiKey, setApiKey] = useState("");
  const [details, setDetails] = useState<ModelDetails>(shippedModel);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsStarting(true);
    setError(null);
    try {
      await addCredential(directUrl, { name: SETUP_MODEL_CREDENTIAL, details, value: apiKey, bot_ids: [ASSISTANT_ID] });
      router.replace("/");
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not reach the harness to save.");
      setIsStarting(false);
    }
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="grid gap-6">
      <div className="grid gap-2 text-center">
        <h1 className="font-serif text-4xl tracking-tight text-balance">Welcome to Cell Harness</h1>
        <p className="text-sm text-ink-soft">Paste your API key to start.</p>
      </div>
      <div className="grid gap-3">
        <Field label="API key" htmlFor="setup-key">
          <input
            id="setup-key"
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            autoFocus
            autoComplete="off"
            spellCheck={false}
            className={INPUT_CLASSES}
          />
        </Field>
        <ProviderFields details={details} onChange={setDetails} />
      </div>
      {error && (
        <p className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm break-words text-danger">
          {error}
        </p>
      )}
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={isStarting}
          className="ml-auto rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-35"
        >
          {isStarting ? "Starting…" : "Start"}
        </button>
      </div>
    </form>
  );
}

interface ProviderFieldsProps {
  details: ModelDetails;
  onChange: (details: ModelDetails) => void;
}

function ProviderFields({ details, onChange }: ProviderFieldsProps) {
  return (
    <>
      <Field label="Endpoint" htmlFor="setup-endpoint">
        <input
          id="setup-endpoint"
          value={details.base_url}
          onChange={(event) => onChange({ ...details, base_url: event.target.value })}
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          className={INPUT_CLASSES}
        />
      </Field>
      <Field label="Model" htmlFor="setup-model">
        <input
          id="setup-model"
          value={details.model}
          onChange={(event) => onChange({ ...details, model: event.target.value })}
          autoComplete="off"
          spellCheck={false}
          className={`font-mono ${INPUT_CLASSES}`}
        />
      </Field>
    </>
  );
}
