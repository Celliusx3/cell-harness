import type { Credential } from "./credentials";
import type { KeyedServer, ServerStatus } from "./types";

/** One env key one capability needs, by the capability's server id. */
export interface CapabilityKey {
  server: string;
  variable: string;
}

const STATUS_LABELS: Record<ServerStatus, string> = {
  waiting: "off until its key is saved",
  connecting: "starting",
  connected: "on",
  failed: "failed",
  disconnected: "off",
};

/** A capability as a person reads it: `places` is Places. */
export function capabilityLabel(server: string): string {
  return server.charAt(0).toUpperCase() + server.slice(1);
}

/** "Places: GOOGLE_MAPS_API_KEY". */
export function capabilityKeyLabel(key: CapabilityKey): string {
  return `${capabilityLabel(key.server)}: ${key.variable}`;
}

export function statusLabel(server: KeyedServer): string {
  return server.status === "failed" && server.error !== "" ? `failed: ${server.error}` : STATUS_LABELS[server.status];
}

/** Every key a capability needs that no credential but `editing` holds yet, in the order the harness lists them. */
export function openCapabilityKeys(keyed: KeyedServer[], credentials: Credential[], editing: string | null): CapabilityKey[] {
  const held = new Set(
    credentials.flatMap(({ name, details }) =>
      details.kind === "capability" && name !== editing ? [heldKey(details)] : [],
    ),
  );
  return keyed
    .flatMap((server) => server.needs.map((variable) => ({ server: server.id, variable })))
    .filter((key) => !held.has(heldKey(key)));
}

/** Whether a capability is still starting, so its state is worth asking for again. */
export function isStarting(keyed: KeyedServer[]): boolean {
  return keyed.some((server) => server.status === "connecting");
}

function heldKey(key: CapabilityKey): string {
  return JSON.stringify([key.server, key.variable]);
}
