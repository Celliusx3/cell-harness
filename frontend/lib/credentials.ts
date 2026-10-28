import { ApiError, detailOf, request } from "./api";

/** The one https origin a custom key may be sent to, and how that site takes the key. */
export interface Destination {
  origin: string;
  auth: "bearer" | "header";
  header_name: string | null;
}

/** What a credential is for, by its kind: a website's key, a model, or a chat platform's token. */
export type CredentialDetails =
  | { kind: "custom"; destination: Destination }
  | { kind: "llm"; base_url: string; model: string }
  | { kind: "telegram" }
  | { kind: "discord" };

/** The kinds that sign the app in to a chat platform. */
export type ChatPlatform = Extract<CredentialDetails["kind"], "telegram" | "discord">;

/** `GET /api/credentials`: one keyring entry, the bots it serves, and its last four characters at most. */
export interface Credential {
  name: string;
  details: CredentialDetails;
  last_four: string | null;
  is_default_model: boolean;
  bots: { id: string; name: string }[];
}

/** `GET /api/credentials`, with the harness's own address, where every save goes. */
export interface CredentialList {
  credentials: Credential[];
  direct_url: string;
}

/** `POST /api/credentials`: a new credential, its key, and the bots it serves. */
export interface CredentialDraft {
  name: string;
  details: CredentialDetails;
  value: string;
  bot_ids: string[];
}

/** `PATCH /api/credentials/{name}`: what it is for, a new key or null to keep the saved one, and its bots. */
export interface CredentialChange {
  details: CredentialDetails;
  value: string | null;
  bot_ids: string[];
}

/** Every credential in the keyring, with its bots, each by its last four characters at most. */
export const listCredentials = () => request<CredentialList>("/credentials");

/** Whether this browser reaches the harness directly, which only a page on its own Mac does. */
export async function canSaveCredentials(directUrl: string): Promise<boolean> {
  try {
    return (await fetch(`${directUrl}/api/credentials`)).ok;
  } catch {
    return false;
  }
}

export const addCredential = (directUrl: string, draft: CredentialDraft) =>
  sendToHarness(directUrl, "", { method: "POST", body: JSON.stringify(draft) });

export const changeCredential = (directUrl: string, name: string, change: CredentialChange) =>
  sendToHarness(directUrl, `/${encodeURIComponent(name)}`, { method: "PATCH", body: JSON.stringify(change) });

/** The credential goes from the keyring and from every bot it served. */
export const removeCredential = (directUrl: string, name: string) =>
  sendToHarness(directUrl, `/${encodeURIComponent(name)}`, { method: "DELETE" });

/** Resolves when the harness at `directUrl` accepts; `ApiError` with its detail when it refuses. */
async function sendToHarness(directUrl: string, path: string, init: { method: string; body?: string }): Promise<void> {
  const response = await fetch(`${directUrl}/api/credentials${path}`, {
    ...init,
    headers: init.body === undefined ? undefined : { "content-type": "application/json" },
  });
  if (!response.ok) throw new ApiError(response.status, await detailOf(response));
}
