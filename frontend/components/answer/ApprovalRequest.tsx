"use client";

import { ShieldQuestion } from "lucide-react";

import type { ClientToolProps } from "@/components/answer/useClientTool";
import { useClientTool } from "@/components/answer/useClientTool";
import { Arguments } from "@/components/conversation/ToolCard";
import { humanise } from "@/lib/toolName";
import type { Decision, Scope } from "@/lib/types";

const ALLOW: { scope: Scope; label: string }[] = [
  { scope: "once", label: "Allow once" },
  { scope: "conversation", label: "Allow for this conversation" },
  { scope: "always", label: "Always allow" },
];

const FILLED =
  "rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90";
const OUTLINED =
  "rounded-lg border border-line bg-surface px-3 py-1 text-xs font-medium transition hover:bg-surface-sunken";

/** The card for a gated call waiting on the person: what it wants, its arguments, and the four answers. */
export function ApprovalRequest(props: ClientToolProps) {
  const { item } = props;
  const { phase, send } = useClientTool<never>(props);
  const { server, label } = humanise(item.call.name);
  const decide = (decision: Decision) => void send(decision);

  return (
    <div className="rounded-xl border border-accent/40 bg-accent-soft px-3 py-2.5 text-sm">
      <div className="flex items-center gap-2">
        <ShieldQuestion size={14} className="shrink-0 text-accent" />
        <span className="font-medium">{label}</span>
        {server !== null && (
          <span className="rounded-md border border-line bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">
            {server}
          </span>
        )}
      </div>
      {phase === "asking" ? (
        <>
          <div className="mt-2 space-y-2">
            <Arguments raw={item.call.arguments} tool={item.call.name} />
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {ALLOW.map(({ scope, label: text }) => (
              <button
                key={scope}
                type="button"
                onClick={() => decide({ kind: "approved", scope })}
                className={FILLED}
              >
                {text}
              </button>
            ))}
            <button
              type="button"
              onClick={() => decide({ kind: "denied" })}
              className={OUTLINED}
            >
              Deny
            </button>
          </div>
        </>
      ) : (
        <p className="mt-2 text-xs text-ink-soft">Sending…</p>
      )}
    </div>
  );
}
