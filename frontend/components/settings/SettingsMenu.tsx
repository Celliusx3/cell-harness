"use client";

import {
  ArrowLeft,
  BookOpen,
  CalendarClock,
  LockKeyhole,
  Server,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Drawer } from "@/components/chat/Drawer";
import { SidebarLink } from "@/components/chat/SidebarLink";
import { chatPathToReturnTo } from "@/components/settings/chatReturn";

interface SettingsLink {
  href: string;
  label: string;
  icon: LucideIcon;
}

const PAGES: SettingsLink[] = [
  { href: "/settings/credentials", label: "Credentials", icon: LockKeyhole },
  { href: "/settings/mcp", label: "MCP servers", icon: Server },
  { href: "/settings/approvals", label: "Approvals", icon: ShieldCheck },
  { href: "/settings/schedules", label: "Schedules", icon: CalendarClock },
  { href: "/settings/skills", label: "Skills", icon: BookOpen },
];

/** The settings pages in the sidebar's place, under a way back to the chats. */
export function SettingsMenu() {
  const pathname = usePathname();
  const [backPath, setBackPath] = useState("/");

  useEffect(() => setBackPath(chatPathToReturnTo()), []);

  return (
    <Drawer>
      <div className="px-2 py-3">
        <SidebarLink href={backPath} label="Back to chats" icon={ArrowLeft} current={false} />
      </div>
      <nav className="space-y-0.5 px-2">
        <h2 className="px-2 pb-1 text-xs font-medium text-ink-soft">Settings</h2>
        {PAGES.map((page) => (
          <SidebarLink key={page.href} {...page} current={pathname === page.href} />
        ))}
      </nav>
    </Drawer>
  );
}
