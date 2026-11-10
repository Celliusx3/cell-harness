"use client";

import { ChevronDown, ShieldAlert, ShieldCheck, TriangleAlert, type LucideIcon } from "lucide-react";
import { useState } from "react";

import {
  Dialog,
  DialogContent,
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

export const MODE_ICONS: Record<ApprovalMode, LucideIcon> = { ask: ShieldCheck, auto: ShieldAlert };

const MODE_DESCRIPTIONS: Record<ApprovalMode, string> = {
  ask: "Ask before a tool changes something",
  auto: "Run every tool without asking",
};

const MODES: ApprovalMode[] = ["ask", "auto"];

const RISK_TITLE = "Switch to Auto?";

const RISK_DESCRIPTION =
  "Auto lets the bot run every tool in this chat without asking, including ones that change files, send messages or run commands. Questions to you still wait for your answer. Only use it when you trust the task.";

const RISK_ACKNOWLEDGEMENT = "I understand the risks and want to continue";

const isApprovalMode = (value: unknown): value is ApprovalMode =>
  MODES.some((mode) => mode === value);

interface Props {
  mode: ApprovalMode;
  onPick(mode: ApprovalMode): void;
  /** Whether the menu is open; a bare `/mode` opens it too. */
  open: boolean;
  onOpenChange(open: boolean): void;
}

/** The chat's mode in the message box; Ask switches at once, Auto only once its risk is acknowledged. */
export function ModePicker({ mode, onPick, open, onOpenChange }: Props) {
  const [confirming, setConfirming] = useState(false);
  const Icon = MODE_ICONS[mode];

  const pick = (value: unknown) => {
    if (!isApprovalMode(value) || value === mode) return;
    if (value === "auto") setConfirming(true);
    else onPick(value);
  };

  return (
    <>
      <DropdownMenu open={open} onOpenChange={onOpenChange}>
        <DropdownMenuTrigger
          aria-label={`Mode: ${MODE_LABELS[mode]}`}
          title={MODE_DESCRIPTIONS[mode]}
          className="group flex h-7 shrink-0 items-center gap-1 rounded-full pr-1 pl-2 text-[13px] font-medium text-ink-soft transition outline-none hover:bg-surface-sunken focus-visible:ring-2 focus-visible:ring-line data-popup-open:bg-surface-sunken"
        >
          <Icon size={14} aria-hidden />
          <span className="hidden sm:inline">{MODE_LABELS[mode]}</span>
          <ChevronDown
            size={14}
            aria-hidden
            className="text-ink-soft/70 transition-transform duration-100 group-data-popup-open:rotate-180"
          />
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="start" className="w-40">
          <DropdownMenuRadioGroup value={mode} onValueChange={pick}>
            {MODES.map((option) => {
              const OptionIcon = MODE_ICONS[option];
              return (
                <DropdownMenuRadioItem key={option} value={option} closeOnClick className="gap-2">
                  <OptionIcon size={16} aria-hidden />
                  {MODE_LABELS[option]}
                </DropdownMenuRadioItem>
              );
            })}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <RiskConfirmation
        open={confirming}
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          onPick("auto");
        }}
      />
    </>
  );
}

interface RiskProps {
  open: boolean;
  onCancel(): void;
  onConfirm(): void;
}

/** The gate before Auto: its confirm stays disabled until the risk is acknowledged. */
function RiskConfirmation({ open, onCancel, onConfirm }: RiskProps) {
  const [acknowledged, setAcknowledged] = useState(false);
  const close = (then: () => void) => {
    setAcknowledged(false);
    then();
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && close(onCancel)}>
      <DialogContent showCloseButton={false} className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>{RISK_TITLE}</DialogTitle>
        </DialogHeader>
        <div className="flex items-start gap-2.5 text-sm leading-relaxed text-ink-soft">
          <TriangleAlert size={18} aria-hidden className="mt-0.5 shrink-0 text-danger" />
          <p>{RISK_DESCRIPTION}</p>
        </div>
        <label className="flex cursor-pointer items-start gap-2.5 text-sm text-ink">
          <input
            type="checkbox"
            autoFocus
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
            className="mt-0.5 size-4 shrink-0 cursor-pointer accent-accent"
          />
          {RISK_ACKNOWLEDGEMENT}
        </label>
        <DialogFooter>
          <button
            type="button"
            onClick={() => close(onCancel)}
            className="min-w-[72px] rounded-lg border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink-soft transition hover:bg-line hover:text-ink"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!acknowledged}
            onClick={() => close(onConfirm)}
            className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90 disabled:cursor-default disabled:opacity-40"
          >
            Enable Auto
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
