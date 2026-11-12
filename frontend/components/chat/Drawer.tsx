"use client";

import { Menu } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

const OPEN = "harness:drawer-open";

const PANEL = "w-72 shrink-0 flex-col border-r border-line bg-surface-sunken";

/** The side panel: beside the page on a wide screen, slid over it on a phone until a link is followed. */
export function Drawer({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => setOpen(false), [pathname]);

  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener(OPEN, show);
    return () => window.removeEventListener(OPEN, show);
  }, []);

  return (
    <>
      {open && (
        <div
          aria-hidden
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
        />
      )}
      <aside
        className={`${PANEL} ${open ? "fixed inset-y-0 left-0 z-50 flex shadow-xl" : "hidden"} md:static md:z-auto md:flex md:shadow-none`}
      >
        {children}
      </aside>
    </>
  );
}

/** Opens the drawer; shown only on a phone, where the drawer is hidden. */
export function DrawerButton() {
  return (
    <button
      type="button"
      aria-label="Open menu"
      title="Open menu"
      onClick={() => window.dispatchEvent(new Event(OPEN))}
      className="-ml-2 flex size-9 shrink-0 items-center justify-center rounded-lg text-ink-soft transition hover:bg-surface-sunken hover:text-ink md:hidden"
    >
      <Menu size={18} />
    </button>
  );
}
