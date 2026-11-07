/** An `ask_for_secret` call read from the timeline: what the key is for, and the body its card posts. */

import { z } from "zod";

import type { ModelDetails } from "@/lib/credentials";
import type { SecretEntry } from "@/lib/api";

const Named = { name: z.string(), label: z.string() };

export const SecretAsk = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("custom"), ...Named, origin: z.url() }),
  z.object({ kind: z.literal("llm"), ...Named, base_url: z.string(), model: z.string(), vision: z.boolean() }),
  z.object({ kind: z.literal("telegram"), ...Named }),
  z.object({ kind: z.literal("discord"), ...Named }),
]);
export type SecretAsk = z.infer<typeof SecretAsk>;

/** The call's arguments as an ask, or null when they do not parse as one. */
export function askOf(raw: string): SecretAsk | null {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  const parsed = SecretAsk.safeParse(value);
  return parsed.success ? parsed.data : null;
}

/** The endpoint, model and vision an LLM ask fills the card with, or null for another kind. */
export function askedModel(ask: SecretAsk | null): ModelDetails | null {
  if (ask?.kind !== "llm") return null;
  return { kind: "llm", base_url: ask.base_url, model: ask.model, vision: ask.vision };
}

/** What the card posts: the key, with the model's fields as edited when it is an LLM's. */
export function secretEntry(value: string, model: ModelDetails | null): SecretEntry {
  return model === null ? { value } : { value, details: model };
}

/** Where the key goes, said under the card's headline; the assistant never sees it. */
export function destinationNote(ask: SecretAsk): string {
  switch (ask.kind) {
    case "custom":
      return `Sent only to ${new URL(ask.origin).host}. The assistant never sees it.`;
    case "llm":
      return "Saved as an LLM credential; pick it for a bot in Edit bot. The assistant never sees the key.";
    case "telegram":
      return "Signs in the app's Telegram bot. The assistant never sees the token.";
    case "discord":
      return "Signs in the app's Discord bot. The assistant never sees the token.";
    default: {
      const _exhaustive: never = ask;
      return _exhaustive;
    }
  }
}
