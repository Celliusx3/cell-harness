import type { LucideIcon } from "lucide-react";
import Link from "next/link";

/** A sidebar link with its icon and name, marked while its page is open. */
export function SidebarLink({
  href,
  label,
  icon: Icon,
  current,
}: {
  href: string;
  label: string;
  icon: LucideIcon;
  current: boolean;
}) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-2 rounded-md px-2 py-2 text-sm transition ${
        current ? "bg-accent-soft font-medium text-ink" : "text-ink-soft hover:bg-line hover:text-ink"
      }`}
    >
      <Icon size={16} className="shrink-0" />
      <span className="truncate">{label}</span>
    </Link>
  );
}
