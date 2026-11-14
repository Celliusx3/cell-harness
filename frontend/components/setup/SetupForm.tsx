"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Field, INPUT_CLASSES, VisionCheck } from "@/components/credentials/CredentialFields";
import { ApiError, ASSISTANT_ID, listBots, updateBot } from "@/lib/api";
import { addCredential, type ModelDetails } from "@/lib/credentials";

const SETUP_MODEL_CREDENTIAL = "first_model";
const NO_MODEL_YET: ModelDetails = { kind: "llm", base_url: "", model: "", vision: false };

interface SetupFormProps {
  directUrl: string;
}

/** The API key saved as Assistant's model, at the endpoint and model the person types. */
export function SetupForm({ directUrl }: SetupFormProps) {
  const router = useRouter();
  const [apiKey, setApiKey] = useState("");
  const [details, setDetails] = useState<ModelDetails>(NO_MODEL_YET);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsStarting(true);
    setError(null);
    try {
      await addCredential(directUrl, { name: SETUP_MODEL_CREDENTIAL, details, value: apiKey, bot_ids: [] });
      await putAssistantOnModel(SETUP_MODEL_CREDENTIAL);
      router.replace("/");
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not reach the harness to save.");
      setIsStarting(false);
    }
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="grid gap-6">
      <div className="grid gap-2 text-center">
        <h1 className="font-display text-4xl font-semibold tracking-tight text-balance">Welcome to Cell Harness</h1>
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
          className="ml-auto rounded-lg bg-action px-3 py-1 text-xs font-medium text-on-action transition hover:opacity-90 disabled:opacity-35"
        >
          {isStarting ? "Starting…" : "Start"}
        </button>
      </div>
    </form>
  );
}

/** Save Assistant as it is, on the LLM credential `name`. */
async function putAssistantOnModel(name: string) {
  const assistant = (await listBots()).find((bot) => bot.id === ASSISTANT_ID);
  if (assistant === undefined) throw new ApiError(404, "The harness lists no Assistant.");
  await updateBot(ASSISTANT_ID, {
    name: assistant.name,
    instructions: assistant.instructions,
    model: name,
    max_workers: assistant.max_workers,
  });
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
          placeholder="https://api.example.com/v1"
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
      <VisionCheck
        id="setup-vision"
        isChecked={details.vision}
        onChange={(vision) => onChange({ ...details, vision })}
      />
    </>
  );
}
