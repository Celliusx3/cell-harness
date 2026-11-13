"use client";

import { useState } from "react";

import { ApiError } from "@/lib/api";
import { stopTicket, type TicketState } from "@/lib/tickets";

const ENDED: ReadonlySet<TicketState> = new Set(["done", "dropped", "stopped"]);

/** Whether a ticket in `state` can still be stopped. */
export function isStoppable(state: TicketState): boolean {
  return !ENDED.has(state);
}

/** Stops a ticket for good after the person confirms, and says why if it could not. */
export function StopTicketButton({ ticketId }: { ticketId: string }) {
  const [error, setError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);

  const stop = async () => {
    if (!window.confirm("Stop this ticket?")) return;
    setStopping(true);
    try {
      await stopTicket(ticketId);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not stop the ticket.");
    } finally {
      setStopping(false);
    }
  };

  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={() => void stop()}
        disabled={stopping}
        className="text-xs text-danger hover:text-ink disabled:opacity-50"
      >
        Stop
      </button>
      {error !== null && <span className="text-xs text-danger">{error}</span>}
    </span>
  );
}
