"use client";

import type { FormEvent } from "react";
import { useState } from "react";

import { POSITION_OPTIONS, roundToHundredMetres } from "@/components/answer/LocationRequest";
import { BADGE, OPTION } from "@/components/answer/QuestionPanel";

const NOT_SHARED = "The user did not share a location.";

interface Answering {
  disabled: boolean;
  onSend: (text: string) => void;
}

/** A worker's options, one tap each, drawn like the assistant's own question. */
export function ChoiceAnswer({ options, disabled, onSend }: Answering & { options: string[] }) {
  return (
    <div className="mt-3 flex flex-col gap-2">
      {options.map((label, index) => (
        <button
          key={index}
          type="button"
          disabled={disabled}
          onClick={() => onSend(label)}
          className={OPTION}
        >
          <span className={BADGE}>{index + 1}</span>{" "}
          <span className="min-w-0 break-words">{label}</span>
        </button>
      ))}
    </div>
  );
}

/** The key a worker asks for, pasted here, saved under its name, and never shown again. */
export function SecretAnswer({ name, disabled, onSend }: Answering & { name: string | null }) {
  const [draft, setDraft] = useState("");
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!draft || disabled) return;
    onSend(draft);
    setDraft("");
  };
  return (
    <form onSubmit={submit} className="mt-2 flex gap-2">
      <input
        type="password"
        autoComplete="off"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        aria-label={name ?? "Key"}
        placeholder="Paste the key here"
        className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2.5 py-1 text-sm outline-none transition focus:border-accent"
      />
      <button
        type="submit"
        disabled={disabled || !draft}
        className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-35"
      >
        Save
      </button>
    </form>
  );
}

/** Where the person is, read from the browser once they agree, sent as the answer. */
export function LocationAnswer({ disabled, onSend }: Answering) {
  const share = () => {
    if (!("geolocation" in navigator)) {
      onSend(NOT_SHARED);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) =>
        onSend(
          `My location: ${roundToHundredMetres(coords.latitude)}, ${roundToHundredMetres(coords.longitude)}`,
        ),
      () => onSend(NOT_SHARED),
      POSITION_OPTIONS,
    );
  };
  return (
    <div className="mt-2 flex gap-2">
      <button
        type="button"
        disabled={disabled}
        onClick={share}
        className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-35"
      >
        Share location
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onSend(NOT_SHARED)}
        className="rounded-lg border border-line bg-surface px-3 py-1 text-xs font-medium transition hover:bg-surface-sunken"
      >
        Don&apos;t share
      </button>
    </div>
  );
}
