import { z } from "zod";

import type { ChatPlatform, Credential, CredentialChange, CredentialDetails, CredentialDraft } from "@/lib/credentials";
import type { Bot } from "@/lib/types";

export const CredentialKind = z.enum(["custom", "llm", "telegram", "discord"]);
export type CredentialKind = z.infer<typeof CredentialKind>;

export const KeyAuth = z.enum(["bearer", "header"]);
export type KeyAuth = z.infer<typeof KeyAuth>;

/** What the dialog's fields hold for any type, as the person typed it. */
export interface CredentialForm {
  kind: CredentialKind;
  name: string;
  origin: string;
  auth: KeyAuth;
  headerName: string;
  baseUrl: string;
  model: string;
  value: string;
  botIds: string[];
}

const EMPTY_FORM: CredentialForm = {
  kind: "custom",
  name: "",
  origin: "",
  auth: "bearer",
  headerName: "",
  baseUrl: "",
  model: "",
  value: "",
  botIds: [],
};

export function isChatPlatform(kind: CredentialKind): kind is ChatPlatform {
  return kind === "telegram" || kind === "discord";
}

/** The types a new credential may take: every one, but a chat platform already saved. */
export function addableKinds(credentials: Credential[]): CredentialKind[] {
  const saved = new Set(credentials.map((credential) => credential.details.kind));
  return CredentialKind.options.filter((kind) => !isChatPlatform(kind) || !saved.has(kind));
}

/** The fields for a new credential, or `credential`'s with its key left empty. */
export function initialForm(credential: Credential | null): CredentialForm {
  if (credential === null) return EMPTY_FORM;
  const shared = { ...EMPTY_FORM, name: credential.name, botIds: credential.bots.map((bot) => bot.id) };
  const details = credential.details;
  switch (details.kind) {
    case "llm":
      return { ...shared, kind: "llm", baseUrl: details.base_url, model: details.model };
    case "custom": {
      const { origin, auth, header_name } = details.destination;
      return { ...shared, kind: "custom", origin, auth, headerName: header_name ?? "" };
    }
    case "telegram":
    case "discord":
      return { ...shared, kind: details.kind };
  }
}

/** `form` set to `kind`, with no bot ticked for a chat platform. */
export function withKind(form: CredentialForm, kind: CredentialKind): CredentialForm {
  return { ...form, kind, botIds: isChatPlatform(kind) ? [] : form.botIds };
}

export function credentialDraft(form: CredentialForm): CredentialDraft {
  return { name: form.name, details: formDetails(form), value: form.value, bot_ids: form.botIds };
}

/** An empty key field sends null, which keeps the saved key. */
export function credentialChange(form: CredentialForm): CredentialChange {
  return {
    details: formDetails(form),
    value: form.value === "" ? null : form.value,
    bot_ids: form.botIds,
  };
}

/** `botIds` with `botId` ticked or not, in the order `bots` lists them. */
export function tickedIds(bots: Bot[], botIds: string[], botId: string, isTicked: boolean): string[] {
  return bots.map((bot) => bot.id).filter((id) => (id === botId ? isTicked : botIds.includes(id)));
}

function formDetails(form: CredentialForm): CredentialDetails {
  switch (form.kind) {
    case "llm":
      return { kind: "llm", base_url: form.baseUrl, model: form.model };
    case "custom": {
      const headerName = form.auth === "header" ? form.headerName : null;
      return { kind: "custom", destination: { origin: form.origin, auth: form.auth, header_name: headerName } };
    }
    case "telegram":
    case "discord":
      return { kind: form.kind };
  }
}
