import { z } from "zod";

export const SERVER = "computer";
export const PREVIEW_URI = "ui://computer/screen";
export const RELAY_META = "io.cell-harness/relay";

const RelayEntry = z.object({ url: z.string().startsWith("/api/relay/") });
export const RelayMeta = z.object({ [RELAY_META]: RelayEntry });

const Failed = z.object({
  isError: z.literal(true),
  content: z.array(z.object({ type: z.string(), text: z.string().optional() })),
});

export function throwIfFailed(result: unknown): void {
  const failed = Failed.safeParse(result);
  if (!failed.success) return;
  const said = failed.data.content.map((block) => block.text ?? "").join("\n").trim();
  throw new Error(said || "The computer refused, and said nothing about why.");
}

export function parsedResult<T>(schema: z.ZodType<T>, result: unknown): T {
  throwIfFailed(result);
  const answer = schema.safeParse(result);
  if (!answer.success) {
    throw new Error("The computer answered with something this page cannot read.");
  }
  return answer.data;
}
