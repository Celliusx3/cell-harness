import { capabilityLabel, statusLabel } from "@/lib/capabilityKeys";
import type { KeyedServer } from "@/lib/types";

/** Each capability that needs a key, the keys it needs, and whether it is on. */
export function CapabilityList({ keyed }: { keyed: KeyedServer[] }) {
  if (keyed.length === 0) return null;
  return (
    <section>
      <h2 className="pb-2 text-xs font-medium text-ink-soft">Capabilities that need a key</h2>
      <ul className="divide-y divide-line rounded-xl border border-line bg-surface-sunken">
        {keyed.map((server) => (
          <li key={server.id} className="flex items-baseline gap-2 px-3 py-2 text-sm">
            <span className="shrink-0">{capabilityLabel(server.id)}</span>
            <span className="min-w-0 break-all font-mono text-xs text-ink-soft">{server.needs.join(", ")}</span>
            <span
              className={`ml-auto min-w-0 break-words text-right text-xs ${server.status === "connected" ? "text-ink" : "text-ink-soft"}`}
            >
              {statusLabel(server)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
