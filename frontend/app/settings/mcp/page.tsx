"use client";

import { useCallback, useEffect, useState } from "react";

import { ServerDialog } from "@/components/mcp/ServerDialog";
import { ServerRow, type ServerActions } from "@/components/mcp/ServerRow";
import { ApiError } from "@/lib/api";
import { listCredentials } from "@/lib/credentials";
import {
  canChangeServers,
  isAnyStarting,
  listMcpServers,
  removeMcpServer,
  restartMcpServer,
  type McpServer,
} from "@/lib/mcpServers";

const STARTING_POLL_MS = 2000;

/** Whether the dialog is shown, and for a new server or which one. */
type DialogState = { isOpen: false } | { isOpen: true; server: McpServer | null };

const CLOSED: DialogState = { isOpen: false };

/** Every MCP server and its state; the person's own added, edited, restarted and removed only on the Mac that runs the harness. */
export default function McpServersPage() {
  const [servers, setServers] = useState<McpServer[]>([]);
  const [directUrl, setDirectUrl] = useState<string | null>(null);
  const [canChange, setCanChange] = useState<boolean | null>(null);
  const [dialog, setDialog] = useState<DialogState>(CLOSED);
  const [error, setError] = useState<string | null>(null);

  const loadServers = useCallback(async () => {
    try {
      const [listed, credentials] = await Promise.all([listMcpServers(), listCredentials()]);
      setServers(listed.servers);
      setDirectUrl(credentials.direct_url);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not load MCP servers.");
    }
  }, []);

  useEffect(() => {
    void loadServers();
  }, [loadServers]);

  useEffect(() => {
    if (!isAnyStarting(servers)) return;
    const timer = window.setTimeout(() => void loadServers(), STARTING_POLL_MS);
    return () => window.clearTimeout(timer);
  }, [servers, loadServers]);

  useEffect(() => {
    if (directUrl === null) return;
    let cancelled = false;
    void canChangeServers(directUrl).then((can) => {
      if (!cancelled) setCanChange(can);
    });
    return () => {
      cancelled = true;
    };
  }, [directUrl]);

  async function act(change: (url: string) => Promise<void>, failure: string) {
    if (directUrl === null) return;
    try {
      await change(directUrl);
      await loadServers();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : failure);
    }
  }

  function handleRemove(server: McpServer) {
    if (!window.confirm(`Remove ${server.id}? Bots lose its tools.`)) return;
    void act((url) => removeMcpServer(url, server.id), "Could not reach the harness to remove it.");
  }

  function actionsFor(server: McpServer): ServerActions {
    const isOwn = canChange === true && !server.built_in;
    return {
      onEdit: isOwn ? () => setDialog({ isOpen: true, server }) : null,
      onRemove: isOwn ? () => handleRemove(server) : null,
      onRestart:
        canChange === true && server.status === "failed"
          ? () => void act((url) => restartMcpServer(url, server.id), "Could not reach the harness to restart it.")
          : null,
    };
  }

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">MCP servers</h1>
        <span className="shrink-0 text-xs text-ink-soft">{servers.length} set up</span>
        {canChange === true && (
          <button
            type="button"
            onClick={() => setDialog({ isOpen: true, server: null })}
            className="ml-auto rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90"
          >
            Add server
          </button>
        )}
      </header>

      {error && (
        <div className="border-b border-danger/30 bg-danger-soft px-6 py-2 text-sm text-danger">{error}</div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        {canChange === false && (
          <p className="mb-3 max-w-2xl text-xs text-ink-soft">Change MCP servers on the Mac that runs the harness.</p>
        )}
        {servers.length === 0 ? (
          <p className="text-sm text-ink-soft">No MCP servers yet.</p>
        ) : (
          <ul className="max-w-2xl divide-y divide-line rounded-xl border border-line bg-surface-sunken">
            {servers.map((server) => (
              <ServerRow key={server.id} server={server} actions={actionsFor(server)} />
            ))}
          </ul>
        )}
      </div>

      {dialog.isOpen && directUrl !== null && (
        <ServerDialog
          directUrl={directUrl}
          server={dialog.server}
          onClose={() => setDialog(CLOSED)}
          onSaved={() => {
            setDialog(CLOSED);
            void loadServers();
          }}
        />
      )}
    </>
  );
}
