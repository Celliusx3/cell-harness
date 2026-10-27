"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api";
import type { ChatPlatform } from "@/lib/credentials";
import { issueLinkCode, type LinkCode } from "@/lib/linkCodes";
import type { Bot } from "@/lib/types";

const PLATFORMS: { platform: ChatPlatform; name: string }[] = [
  { platform: "telegram", name: "Telegram" },
  { platform: "discord", name: "Discord" },
];

const SECOND_MS = 1000;

type Shown =
  | { kind: "nothing" }
  | { kind: "code"; code: LinkCode; expiresAt: number }
  | { kind: "refused"; message: string };

/** A "Link Telegram" and a "Link Discord" button, each showing the code a direct chat sends. */
export function BotLinks({ bot }: { bot: Bot }) {
  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col gap-1.5 px-6 pb-5">
      <h2 className="text-xs text-ink-soft">Chats on other apps</h2>
      <div className="flex flex-col gap-2">
        {PLATFORMS.map(({ platform, name }) => (
          <LinkChat key={platform} bot={bot} platform={platform} name={name} />
        ))}
      </div>
    </section>
  );
}

function LinkChat({ bot, platform, name }: { bot: Bot; platform: ChatPlatform; name: string }) {
  const [shown, setShown] = useState<Shown>({ kind: "nothing" });
  const [busy, setBusy] = useState(false);

  async function link() {
    setBusy(true);
    try {
      const code = await issueLinkCode(bot.id, platform);
      const expiresAt = Date.now() + code.expires_in_seconds * SECOND_MS;
      setShown({ kind: "code", code, expiresAt });
    } catch (err: unknown) {
      const message = err instanceof ApiError ? err.message : `Could not get a ${name} code.`;
      setShown({ kind: "refused", message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-1.5 rounded-xl border border-line bg-surface-sunken px-3 py-2">
      <div>
        <button
          type="button"
          onClick={() => void link()}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink-soft transition hover:bg-line hover:text-ink disabled:opacity-35"
        >
          Link {name}
        </button>
      </div>
      {shown.kind === "code" && (
        <ShownCode name={name} code={shown.code} expiresAt={shown.expiresAt} />
      )}
      {shown.kind === "refused" && <p className="text-sm text-danger">{shown.message}</p>}
    </div>
  );
}

function ShownCode({ name, code, expiresAt }: { name: string; code: LinkCode; expiresAt: number }) {
  const left = useSecondsUntil(expiresAt);
  const minutes = Math.round(code.expires_in_seconds / 60);
  return (
    <div className="flex flex-col gap-1">
      <p className="font-mono text-2xl tracking-[0.3em]">{code.code}</p>
      <p className="text-sm">
        Send this code to your {name} bot within {minutes} minutes. It links that chat to{" "}
        {code.bot_name}.
      </p>
      <p className="text-xs text-ink-soft" aria-live="polite">
        {left > 0 ? `Expires in ${clock(left)}` : "This code has expired. Ask for a new one."}
      </p>
    </div>
  );
}

/** The whole seconds left until `deadline`, ticking down to zero. */
function useSecondsUntil(deadline: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), SECOND_MS);
    return () => window.clearInterval(timer);
  }, [deadline]);
  return Math.max(0, Math.ceil((deadline - now) / SECOND_MS));
}

function clock(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}
