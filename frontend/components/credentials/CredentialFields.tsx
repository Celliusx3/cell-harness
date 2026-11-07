import type { ReactNode } from "react";

import {
  CredentialKind,
  isChatPlatform,
  KeyAuth,
  servesNoBots,
  tickedIds,
  withKind,
  type CredentialForm,
} from "@/components/credentials/credentialForm";
import { capabilityKeyLabel, type CapabilityKey } from "@/lib/capabilityKeys";
import type { Bot } from "@/lib/types";

export const INPUT_CLASSES =
  "rounded-lg border border-line bg-surface-sunken px-2.5 py-1.5 text-sm outline-none focus:border-accent disabled:opacity-60";

const KIND_LABELS: Record<CredentialKind, string> = {
  custom: "Custom",
  llm: "LLM",
  telegram: "Telegram",
  discord: "Discord",
  capability: "Capability key",
};

interface CredentialFieldsProps {
  form: CredentialForm;
  kinds: CredentialKind[];
  isEditing: boolean;
  bots: Bot[];
  capabilityKeys: CapabilityKey[];
  onChange: (form: CredentialForm) => void;
}

/** The type, then that type's fields, the key and the bots; an edit fixes type and name, and a platform's shows its token alone. */
export function CredentialFields({ form, kinds, isEditing, bots, capabilityKeys, onChange }: CredentialFieldsProps) {
  const change = (update: Partial<CredentialForm>) => onChange({ ...form, ...update });
  const isPlatform = isChatPlatform(form.kind);
  const secret = isPlatform ? "token" : "key";
  return (
    <div className="grid gap-3">
      {!(isEditing && isPlatform) && (
        <TypeAndName form={form} kinds={isEditing ? [form.kind] : kinds} isEditing={isEditing} onChange={change} />
      )}
      {form.kind === "custom" && <WebsiteFields form={form} onChange={change} />}
      {form.kind === "llm" && <ModelFields form={form} onChange={change} />}
      {form.kind === "capability" && <CapabilityField form={form} keys={capabilityKeys} onChange={change} />}
      <Field label={isPlatform ? "Token" : "Key"} htmlFor="credential-key">
        <input
          id="credential-key"
          type="password"
          value={form.value}
          onChange={(event) => change({ value: event.target.value })}
          placeholder={isEditing ? `Leave empty to keep the saved ${secret}` : `Paste the ${secret}`}
          autoComplete="off"
          className={INPUT_CLASSES}
        />
      </Field>
      {!servesNoBots(form.kind) && <BotChecks bots={bots} botIds={form.botIds} onChange={(botIds) => change({ botIds })} />}
      {form.kind === "llm" && (
        <p className="text-xs text-ink-soft">A bot uses one model; ticking it here moves it from another.</p>
      )}
    </div>
  );
}

interface TypeAndNameProps {
  form: CredentialForm;
  kinds: CredentialKind[];
  isEditing: boolean;
  onChange: (update: Partial<CredentialForm>) => void;
}

function TypeAndName({ form, kinds, isEditing, onChange }: TypeAndNameProps) {
  return (
    <>
      <Field label="Type" htmlFor="credential-type">
        <select
          id="credential-type"
          value={form.kind}
          disabled={isEditing}
          onChange={(event) => onChange(withKind(form, CredentialKind.parse(event.target.value)))}
          className={INPUT_CLASSES}
        >
          {kinds.map((kind) => (
            <option key={kind} value={kind}>
              {KIND_LABELS[kind]}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Name" htmlFor="credential-name">
        <input
          id="credential-name"
          value={form.name}
          disabled={isEditing}
          onChange={(event) => onChange({ name: event.target.value })}
          placeholder="lowercase letters, digits and _"
          autoComplete="off"
          className={`font-mono ${INPUT_CLASSES}`}
        />
      </Field>
    </>
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
          className={INPUT_CLASSES}
        />
      </Field>
      <Field label="The site takes the key" htmlFor="credential-auth">
        <select
          id="credential-auth"
          value={form.auth}
          onChange={(event) => onChange({ auth: KeyAuth.parse(event.target.value) })}
          className={INPUT_CLASSES}
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
            className={`font-mono ${INPUT_CLASSES}`}
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
          className={INPUT_CLASSES}
        />
      </Field>
      <Field label="Model" htmlFor="credential-model">
        <input
          id="credential-model"
          value={form.model}
          onChange={(event) => onChange({ model: event.target.value })}
          autoComplete="off"
          className={`font-mono ${INPUT_CLASSES}`}
        />
      </Field>
      <VisionCheck id="credential-vision" isChecked={form.vision} onChange={(vision) => onChange({ vision })} />
    </>
  );
}

interface VisionCheckProps {
  id: string;
  isChecked: boolean;
  onChange: (isChecked: boolean) => void;
}

/** Whether the model can see images; a bot on one that cannot is sent no images and no image tools. */
export function VisionCheck({ id, isChecked, onChange }: VisionCheckProps) {
  return (
    <label htmlFor={id} className="flex items-center gap-2 text-sm">
      <input
        id={id}
        type="checkbox"
        checked={isChecked}
        onChange={(event) => onChange(event.target.checked)}
        className="accent-accent"
      />
      Can see images
    </label>
  );
}

interface CapabilityFieldProps extends TypeFieldsProps {
  keys: CapabilityKey[];
}

function CapabilityField({ form, keys, onChange }: CapabilityFieldProps) {
  const chosen = keys.findIndex((key) => key.server === form.server && key.variable === form.variable);
  const choose = (index: string) => {
    const key = keys[Number(index)];
    if (key !== undefined) onChange({ server: key.server, variable: key.variable });
  };
  return (
    <Field label="Capability" htmlFor="credential-capability">
      <select
        id="credential-capability"
        value={chosen === -1 ? "" : String(chosen)}
        onChange={(event) => choose(event.target.value)}
        className={INPUT_CLASSES}
      >
        <option value="" disabled>
          Choose the key a capability needs
        </option>
        {keys.map((key, index) => (
          <option key={capabilityKeyLabel(key)} value={String(index)}>
            {capabilityKeyLabel(key)}
          </option>
        ))}
      </select>
    </Field>
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

export function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs text-ink-soft" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
    </div>
  );
}
