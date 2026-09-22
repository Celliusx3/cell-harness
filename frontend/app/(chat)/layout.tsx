import { Sidebar } from "@/components/chat/Sidebar";

/** The chat: a sidebar of conversations beside the one open. */
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
