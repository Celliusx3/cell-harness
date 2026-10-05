import { Sidebar } from "@/components/chat/Sidebar";

/** The chat: a sidebar of bots beside the chat open. */
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
