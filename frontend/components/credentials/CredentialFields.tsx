import type { ReactNode } from "react";

import {
  EditableKind,
  KeyAuth,
  tickedIds,
  type CredentialForm,
} from "@/components/credentials/credentialForm";
import type { Bot } from "@/lib/types";

const INPUT =
  "rounded-lg border border-line bg-surface-sunken px-2.5 py-1.5 text-sm outline-none focus:border-accent disabled:opacity-60";

interface CredentialFieldsProps {
  form: CredentialForm;
  isEditing: boolean;
  bots: Bot[];
  onChange: (form: CredentialForm) => void;
}

/** The type, then that type's fields, the key and the bots; type and name are fixed on an edit. */
export function CredentialFields({ form, isEditing, bots, onChange }: CredentialFieldsProps) {
  const change = (update: Partial<CredentialForm>) => onChange({ ...form, ...update });
  return (
    <div className="grid gap-3">
      <Field label="Type" htmlFor="credential-type">
        <select
          id="credential-type"
          value={form.kind}
          disabled={isEditing}
          onChange={(event) => change({ kind: EditableKind.parse(event.target.value) })}
          className={INPUT}
        >
          <option value="custom">Custom</option>
          <option value="llm">LLM</option>
        </select>
      </Field>
      <Field label="Name" htmlFor="credential-name">
        <input
          id="credential-name"
          value={form.name}
          disabled={isEditing}
          onChange={(event) => change({ name: event.target.value })}
          placeholder="lowercase letters, digits and _"
          autoComplete="off"
          className={`font-mono ${INPUT}`}
        />
      </Field>
      {form.kind === "custom" ? <WebsiteFields form={form} onChange={change} /> : <ModelFields form={form} onChange={change} />}
      <Field label="Key" htmlFor="credential-key">
        <input
          id="credential-key"
          type="password"
          value={form.value}
          onChange={(event) => change({ value: event.target.value })}
          placeholder={isEditing ? "Leave empty to keep the saved key" : "Paste the key"}
          autoComplete="off"
          className={INPUT}
        />
      </Field>
      <BotChecks bots={bots} botIds={form.botIds} onChange={(botIds) => change({ botIds })} />
      {form.kind === "llm" && (
        <p className="text-xs text-ink-soft">A bot uses one model; ticking it here moves it from another.</p>
      )}
    </div>
  );
}

interface TypeFieldsProps {
  form: CredentialForm;
  onChange: (update: Partial<CredentialForm>) => void;
}

function WebsiteFields({ form, onChange }: TypeFieldsProps) {
  return (
    <>
      <Field label="Website" htmlFor="credential-origin">
        <input
          id="credential-origin"
          value={form.origin}
          onChange={(event) => onChange({ origin: event.target.value })}
          placeholder="https://api.example.com"
          inputMode="url"
          autoComplete="off"
          className={INPUT}
        />
      </Field>
      <Field label="The site takes the key" htmlFor="credential-auth">
        <select
          id="credential-auth"
          value={form.auth}
          onChange={(event) => onChange({ auth: KeyAuth.parse(event.target.value) })}
          className={INPUT}
        >
          <option value="bearer">As a bearer token</option>
          <option value="header">In a header</option>
        </select>
      </Field>
      {form.auth === "header" && (
        <Field label="Header name" htmlFor="credential-header">
          <input
            id="credential-header"
            value={form.headerName}
            onChange={(event) => onChange({ headerName: event.target.value })}
            placeholder="X-Api-Key"
            autoComplete="off"
            className={`font-mono ${INPUT}`}
          />
        </Field>
      )}
    </>
  );
}

function ModelFields({ form, onChange }: TypeFieldsProps) {
  return (
    <>
      <Field label="Endpoint" htmlFor="credential-endpoint">
        <input
          id="credential-endpoint"
          value={form.baseUrl}
          onChange={(event) => onChange({ baseUrl: event.target.value })}
          placeholder="https://api.openai.com/v1"
          inputMode="url"
          autoComplete="off"
          className={INPUT}
        />
      </Field>
      <Field label="Model" htmlFor="credential-model">
        <input
          id="credential-model"
          value={form.model}
          onChange={(event) => onChange({ model: event.target.value })}
          autoComplete="off"
          className={`font-mono ${INPUT}`}
        />
      </Field>
    </>
  );
}

interface BotChecksProps {
  bots: Bot[];
  botIds: string[];
  onChange: (botIds: string[]) => void;
}

function BotChecks({ bots, botIds, onChange }: BotChecksProps) {
  return (
    <fieldset className="flex flex-col">
      <legend className="pb-1.5 text-xs text-ink-soft">Bots</legend>
      <ul className="max-h-40 divide-y divide-line overflow-y-auto rounded-xl border border-line bg-surface-sunken">
        {bots.map((bot) => (
          <li key={bot.id}>
            <label className="flex items-center gap-2 px-3 py-1.5 text-sm">
              <input
                type="checkbox"
                checked={botIds.includes(bot.id)}
                onChange={(event) => onChange(tickedIds(bots, botIds, bot.id, event.target.checked))}
                className="accent-accent"
              />
              <span className="min-w-0 break-words">{bot.name}</span>
            </label>
          </li>
        ))}
      </ul>
    </fieldset>
  );
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs text-ink-soft" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
    </div>
  );
}
