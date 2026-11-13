"use client";

import { ShieldQuestion } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

import { APPROVAL_OPTIONS } from "@/components/answer/ApprovalPanel";
import { POSITION_OPTIONS, roundToHundredMetres } from "@/components/answer/LocationRequest";
import { BADGE, OPTION } from "@/components/answer/answerStyles";
import { Arguments } from "@/components/conversation/ToolCard";
import { humanise } from "@/lib/toolName";
import type { Decision, ToolCall } from "@/lib/types";

const NOT_SHARED = "The user did not share a location.";

interface Answering {
  disabled: boolean;
  onSend: (text: string) => void;
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
        className="rounded-lg bg-action px-3 py-1 text-xs font-medium text-on-action transition hover:opacity-90 disabled:opacity-35"
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
        className="rounded-lg bg-action px-3 py-1 text-xs font-medium text-on-action transition hover:opacity-90 disabled:opacity-35"
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

/** The call a worker waits to have allowed, with its arguments, and the bot's own four choices. */
export function ApprovalAnswer({
  call,
  disabled,
  onDecide,
}: {
  call: ToolCall | null;
  disabled: boolean;
  onDecide: (decision: Decision) => void;
}) {
  const { server, label } = humanise(call?.name ?? "");
  return (
    <>
      {call !== null && (
        <>
          <div className="mt-2 flex items-center gap-2 text-sm">
            <ShieldQuestion size={14} className="shrink-0 text-attention" />
            <span className="min-w-0 break-words font-medium">{label}</span>
            {server !== null && (
              <span className="rounded-md border border-line bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">
                {server}
              </span>
            )}
          </div>
          <div className="mt-2 space-y-2">
            <Arguments raw={call.arguments} tool={call.name} />
          </div>
        </>
      )}
      <div className="mt-3 flex flex-col gap-2">
        {APPROVAL_OPTIONS.map((option, index) => (
          <button
            key={option.label}
            type="button"
            disabled={disabled}
            onClick={() => onDecide(option.decision)}
            className={OPTION}
          >
            <span className={BADGE}>{index + 1}</span>{" "}
            <span className="min-w-0 break-words">{option.label}</span>
          </button>
        ))}
      </div>
    </>
  );
}
