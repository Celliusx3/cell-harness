import { useSyncExternalStore } from "react";

type Listener = () => void;

let workingChatId: string | null = null;
let listeners: readonly Listener[] = [];

function nextWorkingChat(current: string | null, chatId: string, working: boolean): string | null {
  if (working) return chatId;
  return current === chatId ? null : current;
}

/** Marks a chat's bot as working, or clears it if that chat was the one working. */
export function announceWorking(chatId: string, working: boolean): void {
  const next = nextWorkingChat(workingChatId, chatId, working);
  if (next === workingChatId) return;
  workingChatId = next;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: Listener): () => void {
  listeners = [...listeners, listener];
  return () => {
    listeners = listeners.filter((other) => other !== listener);
  };
}

function currentWorkingChat(): string | null {
  return workingChatId;
}

function serverWorkingChat(): null {
  return null;
}

/** The id of the chat whose bot is working now, or null. */
export function useWorkingChat(): string | null {
  return useSyncExternalStore(subscribe, currentWorkingChat, serverWorkingChat);
}
