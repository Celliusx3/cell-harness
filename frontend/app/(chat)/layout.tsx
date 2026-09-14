import { Sidebar } from "@/components/Sidebar";

/**
 * The chat: a sidebar of conversations beside the one open.
 *
 * A route group rather than the root layout, because `/apps/…` — an MCP App on
 * its own page, opened from a phone — is the one route that must not have it.
 */
export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </>
  );
}
