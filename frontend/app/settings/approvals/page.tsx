"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, listApprovals, revokeApproval } from "@/lib/api";
import { humanise } from "@/lib/toolName";

/** The tools allowed always, each with a way to make it ask again. */
export default function ApprovalsPage() {
  const [tools, setTools] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setTools((await listApprovals()).tools);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not load approvals.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const revoke = async (tool: string) => {
    try {
      await revokeApproval(tool);
    } catch (err: unknown) {
      const alreadyGone = err instanceof ApiError && err.status === 404;
      if (!alreadyGone) {
        setError(err instanceof ApiError ? err.message : "Could not revoke.");
        return;
      }
    }
    await refresh();
  };

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">Approvals</h1>
        <span className="shrink-0 text-xs text-ink-soft">{tools.length} allowed always</span>
      </header>

      {error && (
        <div className="border-b border-danger/30 bg-danger-soft px-6 py-2 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        {tools.length === 0 ? (
          <p className="text-sm text-ink-soft">Nothing is allowed always.</p>
        ) : (
          <ul className="max-w-2xl divide-y divide-line rounded-xl border border-line bg-surface-sunken">
            {tools.map((tool) => (
              <ApprovalRow key={tool} tool={tool} onRevoke={() => void revoke(tool)} />
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

function ApprovalRow({ tool, onRevoke }: { tool: string; onRevoke: () => void }) {
  const { server, label } = humanise(tool);
  return (
    <li className="flex items-center gap-2 px-3 py-2 text-sm">
      <span className="font-medium">{label}</span>
      {server !== null && (
        <span className="rounded-md border border-line bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">
          {server}
        </span>
      )}
      <button
        type="button"
        onClick={onRevoke}
        className="ml-auto rounded-lg border border-line bg-surface px-3 py-1 text-xs font-medium transition hover:bg-surface-sunken"
      >
        Revoke
      </button>
    </li>
  );
}
