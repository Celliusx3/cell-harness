import { commandLine, stateLabel, type McpServer } from "@/lib/mcpServers";

const ROW_BUTTON =
  "shrink-0 rounded-md border border-line bg-surface px-2 py-0.5 text-xs text-ink-soft transition hover:bg-line hover:text-ink";

/** What the person may do to a server from this page; null for an action not offered. */
export interface ServerActions {
  onEdit: (() => void) | null;
  onRemove: (() => void) | null;
  onRestart: (() => void) | null;
}

/** One server: its name, its command line, whether it is built in, its state, each key set or missing, and what may be done to it. */
export function ServerRow({ server, actions }: { server: McpServer; actions: ServerActions }) {
  return (
    <li className="px-3 py-2 text-sm">
      <div className="flex items-baseline gap-2">
        <span className="min-w-0 break-all font-mono text-[13px]">{server.id}</span>
        {server.built_in && <span className="shrink-0 text-xs font-medium text-ink">Built in</span>}
        <span className={`ml-auto min-w-0 break-words text-right text-xs ${stateColor(server)}`}>
          {stateLabel(server)}
        </span>
      </div>
      <p className="mt-1 break-all font-mono text-xs text-ink-soft">{commandLine(server)}</p>
      <div className="mt-1 flex items-center gap-2">
        <ul className="min-w-0 flex-1 text-xs text-ink-soft">
          {server.keys.map((key) => (
            <li key={key.name} className="break-all">
              <span className="font-mono">{key.name}</span> {key.is_set ? "set" : "missing"}
            </li>
          ))}
        </ul>
        <RowButton label="Restart" onClick={actions.onRestart} />
        <RowButton label="Edit" onClick={actions.onEdit} />
        <RowButton label="Remove" onClick={actions.onRemove} />
      </div>
    </li>
  );
}

function RowButton({ label, onClick }: { label: string; onClick: (() => void) | null }) {
  if (onClick === null) return null;
  return (
    <button type="button" onClick={onClick} className={ROW_BUTTON}>
      {label}
    </button>
  );
}

function stateColor(server: McpServer): string {
  if (server.status === "failed") return "text-danger";
  return server.status === "connected" ? "text-ink" : "text-ink-soft";
}
