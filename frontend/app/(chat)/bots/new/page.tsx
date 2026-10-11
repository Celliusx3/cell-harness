"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { BotSuggestions } from "@/components/bots/BotSuggestions";
import { Composer } from "@/components/conversation/Composer";
import { ApiError, BUILDER_ID, clearConversation, sendMessage } from "@/lib/api";

interface Seed {
  key: number;
  draft: string;
}

/** A new bot, described to the bot builder; sending starts a fresh builder chat. */
export default function NewBotPage() {
  const router = useRouter();
  const [seed, setSeed] = useState<Seed>({ key: 0, draft: "" });
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reseed = (draft: string) => setSeed((current) => ({ key: current.key + 1, draft }));

  async function start(prompt: string) {
    if (running) return;
    setRunning(true);
    setError(null);
    try {
      await clearConversation(BUILDER_ID);
      await sendMessage(BUILDER_ID, prompt);
      router.push(`/c/${BUILDER_ID}`);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not start the bot builder.");
      setRunning(false);
      reseed(prompt);
    }
  }

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">New bot</h1>
      </header>
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-6">
        <div className="m-auto flex w-full max-w-3xl flex-col gap-6">
          <div className="flex flex-col items-center gap-2 text-center">
            <h2 className="font-serif text-4xl tracking-tight">What kind of bot do you want?</h2>
            <p className="text-sm text-ink-soft">
              Pick a kind and finish the sentence, or describe your own.
            </p>
          </div>
          <BotSuggestions onPick={reseed} />
          {error && <p className="text-sm text-danger">{error}</p>}
        </div>
      </div>
      <Composer
        key={seed.key}
        autoFocus
        initialDraft={seed.draft}
        running={running}
        onSend={(prompt) => void start(prompt)}
        onStop={() => undefined}
      />
    </>
  );
}
