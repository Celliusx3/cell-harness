"use client";

import { type ReactNode, useState } from "react";

import { type TurnUsage, usageLine } from "@/components/conversation/usage";

/** A reply with its turn's usage under it, shown on hover, or on tap where nothing hovers. */
export function ReplyUsage({ usage, children }: { usage: TurnUsage | null; children: ReactNode }) {
  const [tapped, setTapped] = useState(false);
  if (usage === null) return <>{children}</>;
  const onTap = () => {
    if (window.matchMedia("(hover: none)").matches) setTapped((shown) => !shown);
  };
  return (
    <div className="group" onClick={onTap}>
      {children}
      <p
        className={`mt-1 pl-10 text-xs text-ink-soft transition-opacity group-hover:opacity-100 ${
          tapped ? "opacity-100" : "opacity-0"
        }`}
      >
        {usageLine(usage)}
      </p>
    </div>
  );
}
