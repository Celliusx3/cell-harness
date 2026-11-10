"use client";

import { ChevronDown, ShieldQuestion, Zap, type LucideIcon } from "lucide-react";
import { useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ApprovalMode } from "@/lib/types";

export const MODE_LABELS: Record<ApprovalMode, string> = { ask: "Ask", auto: "Auto" };

const MODE_DESCRIPTIONS: Record<ApprovalMode, string> = {
  ask: "Ask before a tool changes something",
  auto: "Run every tool without asking",
};

const MODE_ICONS: Record<ApprovalMode, LucideIcon> = { ask: ShieldQuestion, auto: Zap };

const MODES: ApprovalMode[] = ["ask", "auto"];

const AUTO_CONFIRMATION = "Let this bot act without asking in this chat?";

const AUTO_CONSEQUENCE =
  "Tools that change something will run with no approval card. A question to you, such as a request for your location, still waits for your answer. You can switch back to Ask at any time.";

const isApprovalMode = (value: unknown): value is ApprovalMode =>
  MODES.some((mode) => mode === value);

interface Props {
  mode: ApprovalMode;
  onPick(mode: ApprovalMode): void;
}

/** The chat's mode in the message box; Ask switches at once, Auto only once confirmed. */
export function ModePicker({ mode, onPick }: Props) {
  const [confirming, setConfirming] = useState(false);
  const Icon = MODE_ICONS[mode];

  const pick = (value: unknown) => {
    if (!isApprovalMode(value) || value === mode) return;
    if (value === "auto") setConfirming(true);
    else onPick(value);
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label={`Mode: ${MODE_LABELS[mode]}`}
          title="Choose how much the bot may do without asking"
          className="flex h-9 shrink-0 items-center gap-1 rounded-xl px-2 text-xs font-medium text-ink-soft transition hover:bg-surface-sunken hover:text-ink data-popup-open:bg-surface-sunken data-popup-open:text-ink"
        >
          <Icon size={14} />
          {MODE_LABELS[mode]}
          <ChevronDown size={12} />
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="start" className="w-64">
          <DropdownMenuRadioGroup value={mode} onValueChange={pick}>
            {MODES.map((option) => (
              <DropdownMenuRadioItem
                key={option}
                value={option}
                closeOnClick
                className="px-2.5 py-2"
              >
                <span className="flex flex-col">
                  {MODE_LABELS[option]}
                  <span className="text-xs text-ink-soft">{MODE_DESCRIPTIONS[option]}</span>
                </span>
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>{AUTO_CONFIRMATION}</DialogTitle>
            <DialogDescription>{AUTO_CONSEQUENCE}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="rounded-lg border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink-soft transition hover:bg-line hover:text-ink"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                setConfirming(false);
                onPick("auto");
              }}
              className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90"
            >
              Switch to Auto
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
