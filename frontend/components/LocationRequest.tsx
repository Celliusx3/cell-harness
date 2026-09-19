"use client";

import { MapPin } from "lucide-react";
import { useEffect } from "react";

import type { ClientToolProps, Phase } from "@/lib/clientTools";
import { useClientTool } from "@/lib/clientTools";
import type { ToolItem } from "@/lib/timeline";
import type { Location } from "@/lib/types";

const POSITION_OPTIONS: PositionOptions = {
  enableHighAccuracy: false,
  timeout: 15_000,
  maximumAge: 60_000,
};

/** The browser's error codes, by name */
const REASONS = [
  "PERMISSION_DENIED",
  "POSITION_UNAVAILABLE",
  "TIMEOUT",
] as const;

const roundToHundredMetres = (value: number) => Math.round(value * 1000) / 1000;

/** The card for a pending `get_location` call. */
export function LocationRequest(props: ClientToolProps) {
  const { item } = props;
  const { pending, phase, setPhase, decided, send } =
    useClientTool<Location>(props);

  const share = () => {
    decided.current = true;
    setPhase("working");
    if (!("geolocation" in navigator)) {
      void send({ kind: "unavailable", reason: "POSITION_UNAVAILABLE" });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) =>
        void send({
          kind: "shared",
          data: {
            latitude: roundToHundredMetres(coords.latitude),
            longitude: roundToHundredMetres(coords.longitude),
            accuracy_m: Math.round(coords.accuracy),
          },
        }),
      (error) =>
        void send({
          kind: "unavailable",
          reason: REASONS[error.code - 1] ?? "POSITION_UNAVAILABLE",
        }),
      POSITION_OPTIONS,
    );
  };

  useEffect(() => {
    if (!pending || decided.current) return;
    // Safari has no permissions query for geolocation, so `prompt` is assumed.
    const query = navigator.permissions?.query({ name: "geolocation" });
    if (!query) return;
    query.then(
      (status) => {
        if (decided.current) return;
        if (status.state === "granted") share();
        else if (status.state === "denied")
          void send({ kind: "unavailable", reason: "PERMISSION_DENIED" });
      },
      () => undefined,
    );
  }, [pending]);

  return (
    <div className="rounded-xl border border-accent/40 bg-accent-soft px-3 py-2.5 text-sm">
      <div className="flex items-center gap-2">
        <MapPin size={14} className="shrink-0 text-accent" />
        <span className="font-medium">{headline(item, pending, phase)}</span>
      </div>
      {pending && phase === "asking" && (
        <div className="mt-2 flex gap-2">
          <button
            onClick={share}
            className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90"
          >
            Share location
          </button>
          <button
            onClick={() => void send({ kind: "declined" })}
            className="rounded-lg border border-line bg-surface px-3 py-1 text-xs font-medium transition hover:bg-surface-sunken"
          >
            Don&apos;t share
          </button>
        </div>
      )}
    </div>
  );
}

/** What the card says, from the result when there is one. */
function headline(item: ToolItem, pending: boolean, phase: Phase): string {
  if (pending) {
    if (phase === "working") return "Finding your location…";
    if (phase === "sent") return "Sent. Waiting for the assistant…";
    return "The assistant needs your location to answer.";
  }
  switch (item.error) {
    case null:
      return "Location shared.";
    case "DECLINED":
      return "Location not shared.";
    case "UNAVAILABLE":
      return "Your browser couldn't get a location.";
    case "SKIPPED":
      return "Skipped — you continued without sharing.";
    default:
      return "Location request cancelled.";
  }
}
