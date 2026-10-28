import { request } from "./api";
import type { ChatPlatform } from "./credentials";

/** `POST /api/bots/{id}/link-codes`: a code that links one direct chat to the bot, and how long it lasts. */
export interface LinkCode {
  code: string;
  expires_in_seconds: number;
  bot_name: string;
}

/** A fresh code that links a Telegram or Discord direct chat to this bot, voiding the one before. */
export const issueLinkCode = (botId: string, platform: ChatPlatform) =>
  request<LinkCode>(`/bots/${encodeURIComponent(botId)}/link-codes`, {
    method: "POST",
    body: JSON.stringify({ platform }),
  });
