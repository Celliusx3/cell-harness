/** Token usage added up from the logged `assistant/message` events, as one line of text. */

import type { Usage } from "@/lib/types";

export type TurnUsage =
  | { kind: "reported"; input: number; output: number; cached: number | null }
  | { kind: "not_reported" };

/** A turn's steps added up: none reported if one step has no usage, cache only if every step has it. */
export function turnUsage(steps: (Usage | null)[]): TurnUsage | null {
  if (steps.length === 0) return null;
  if (steps.some((usage) => usage === null)) return { kind: "not_reported" };
  const reported = steps as Usage[];
  const cached = reported.map((usage) => usage.cached_input_tokens);
  return {
    kind: "reported",
    input: sum(reported.map((usage) => usage.input_tokens)),
    output: sum(reported.map((usage) => usage.output_tokens)),
    cached: cached.every((count) => count !== null) ? sum(cached as number[]) : null,
  };
}

export function usageLine(usage: TurnUsage): string {
  if (usage.kind === "not_reported") return "usage not reported";
  const said = `${tokens(usage.input)} in · ${tokens(usage.output)} out`;
  if (usage.cached === null) return `${said} · cache not reported`;
  return `${said} · ${tokens(usage.cached)} cached (${hitRate(usage.cached, usage.input)})`;
}

export function tokens(count: number): string {
  if (count < 1_000) return String(count);
  if (count < 1_000_000) return `${shortened(count / 1_000)}k`;
  return `${shortened(count / 1_000_000)}M`;
}

export function hitRate(cached: number, input: number): string {
  return input === 0 ? "0%" : `${Math.round((cached / input) * 100)}%`;
}

function shortened(value: number): string {
  return value.toFixed(1).replace(/\.0$/, "");
}

function sum(counts: number[]): number {
  return counts.reduce((total, count) => total + count, 0);
}
