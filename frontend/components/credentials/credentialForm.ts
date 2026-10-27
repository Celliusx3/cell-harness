import { z } from "zod";

import type { Credential, CredentialChange, CredentialDraft, EditableDetails } from "@/lib/credentials";
import type { Bot } from "@/lib/types";

export const EditableKind = z.enum(["custom", "llm"]);
export type EditableKind = z.infer<typeof EditableKind>;

export const KeyAuth = z.enum(["bearer", "header"]);
export type KeyAuth = z.infer<typeof KeyAuth>;

/** A credential the dialog edits: a website's key or a model. */
export type EditableCredential = Omit<Credential, "details"> & { details: EditableDetails };

/** What the dialog's fields hold for either type, as the person typed it. */
export interface CredentialForm {
  kind: EditableKind;
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

export function isEditable(credential: Credential): credential is EditableCredential {
  return credential.details.kind === "custom" || credential.details.kind === "llm";
}

/** The fields for a new credential, or `credential`'s with its key left empty. */
export function initialForm(credential: EditableCredential | null): CredentialForm {
  if (credential === null) return EMPTY_FORM;
  const shared = { ...EMPTY_FORM, name: credential.name, botIds: credential.bots.map((bot) => bot.id) };
  const details = credential.details;
  if (details.kind === "llm") {
    return { ...shared, kind: "llm", baseUrl: details.base_url, model: details.model };
  }
  const { origin, auth, header_name } = details.destination;
  return { ...shared, kind: "custom", origin, auth, headerName: header_name ?? "" };
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

function formDetails(form: CredentialForm): EditableDetails {
  if (form.kind === "llm") return { kind: "llm", base_url: form.baseUrl, model: form.model };
  const headerName = form.auth === "header" ? form.headerName : null;
  return { kind: "custom", destination: { origin: form.origin, auth: form.auth, header_name: headerName } };
}
