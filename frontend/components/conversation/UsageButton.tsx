"use client";

import { Popover } from "@base-ui/react/popover";
import { Gauge } from "lucide-react";

import { type UsageSummary, usageRows } from "@/components/conversation/usage";

const HOVER_DELAY_MS = 150;

/** An icon beside Attach that shows the chat's token usage on hover or click. */
export function UsageButton({ usage }: { usage: UsageSummary | null }) {
  if (usage === null) return null;
  return (
    <Popover.Root>
      <Popover.Trigger
        openOnHover
        delay={HOVER_DELAY_MS}
        aria-label="Token usage"
        className="flex size-9 shrink-0 items-center justify-center rounded-xl text-ink-soft transition hover:bg-surface-sunken hover:text-ink data-popup-open:bg-surface-sunken data-popup-open:text-ink"
      >
        <Gauge size={16} />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner side="top" align="start" sideOffset={6} className="isolate z-50">
          <Popover.Popup className="w-56 rounded-lg bg-popover p-3 text-popover-foreground shadow-md ring-1 ring-foreground/10 outline-none">
            <Popover.Title className="mb-2 text-xs font-semibold text-ink">
              Token usage · this chat
            </Popover.Title>
            <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-xs">
              {usageRows(usage).map(([label, value]) => (
                <div key={label} className="contents">
                  <dt className="text-ink-soft">{label}</dt>
                  <dd className="text-right tabular-nums text-ink">{value}</dd>
                </div>
              ))}
            </dl>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}
