/** A chat's token usage, added up from its logged `assistant/message` events. */

import type { Usage } from "@/lib/types";

export type UsageSummary =
  | { kind: "reported"; input: number; output: number; cached: number | null }
  | { kind: "not_reported" };

const NOT_REPORTED = "not reported";

/** A chat's steps added up: one with no usage adds nothing, one with no cache figure adds 0 cached. */
export function chatUsage(steps: (Usage | null)[]): UsageSummary | null {
  if (steps.length === 0) return null;
  const reported = steps.filter((usage) => usage !== null);
  if (reported.length === 0) return { kind: "not_reported" };
  const cached = reported.flatMap((usage) => usage.cached_input_tokens ?? []);
  return {
    kind: "reported",
    input: sum(reported.map((usage) => usage.input_tokens)),
    output: sum(reported.map((usage) => usage.output_tokens)),
    cached: cached.length > 0 ? sum(cached) : null,
  };
}

/** The summary as label and value rows, "not reported" where a figure is missing. */
export function usageRows(usage: UsageSummary): [string, string][] {
  if (usage.kind === "not_reported") {
    return ["Input", "Cached", "Output", "Cache hit rate"].map((label) => [label, NOT_REPORTED]);
  }
  const { input, output, cached } = usage;
  return [
    ["Input", tokens(input)],
    ["Cached", cached === null ? NOT_REPORTED : tokens(cached)],
    ["Output", tokens(output)],
    ["Cache hit rate", cached === null ? NOT_REPORTED : hitRate(cached, input)],
  ];
}

function tokens(count: number): string {
  return count.toLocaleString("en-US");
}

function hitRate(cached: number, input: number): string {
  return input === 0 ? "0%" : `${Math.round((cached / input) * 100)}%`;
}

function sum(counts: number[]): number {
  return counts.reduce((total, count) => total + count, 0);
}
