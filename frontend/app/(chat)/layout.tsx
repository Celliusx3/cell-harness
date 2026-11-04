import { Sidebar } from "@/components/chat/Sidebar";
import { SetupGate } from "@/components/setup/SetupGate";

/** The chat: a sidebar of bots beside the chat open, once setup is done. */
export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SetupGate>
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </SetupGate>
  );
}
