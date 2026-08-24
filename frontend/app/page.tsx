"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Composer } from "@/components/Composer";
import { ApiError, createConversation } from "@/lib/api";

/**
 * The empty state, and where a conversation is born.
 *
 * There is no "new conversation" request: phase 3's `create()` writes nothing
 * until a first append, so an id handed out before the first message would be
 * absent from the sidebar and gone on refresh. Sending is what creates.
 */
export default function NewConversationPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const send = async (prompt: string) => {
    setSending(true);
    setError(null);
    try {
      const created = await createConversation(prompt);
      // The turn is already running by the time this resolves. The conversation
      // page opens, fetches its snapshot and subscribes — picking up a stream it
      // did not start, which is the same path a refresh takes.
      router.push(`/c/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "could not start a conversation");
      setSending(false);
    }
  };

  return (
    <>
      <div className="flex flex-1 flex-col items-center justify-center px-4">
        <h1 className="text-2xl font-semibold tracking-tight">What can I help with?</h1>
        <p className="mt-2 text-sm text-ink-soft">
          Turns keep running if you close the tab. Come back and pick them up.
        </p>
        {error && <p className="mt-4 text-sm text-danger">{error}</p>}
      </div>
      <Composer autoFocus running={sending} onSend={send} onStop={() => {}} />
    </>
  );
}
