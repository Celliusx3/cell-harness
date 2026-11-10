import { useEffect, useRef } from "react";

export type AppEvent =
  | { type: "app/connected" }
  | { type: "chat/turn-started"; chat_id: string }
  | { type: "bots/changed" };

type AppEventType = AppEvent["type"];

type Listener = (event: AppEvent) => void;

const APP_EVENTS_URL = "/api/app-events";

const APP_EVENT_TYPES: readonly AppEventType[] = [
  "app/connected",
  "chat/turn-started",
  "bots/changed",
];

let listeners: readonly Listener[] = [];
let source: EventSource | null = null;

function isObject(value: unknown): value is { [key: string]: unknown } {
  return typeof value === "object" && value !== null;
}

/** The event `data` carries, if it is an object whose `type` is `type`; null otherwise. */
function appEventOf(type: AppEventType, data: unknown): AppEvent | null {
  if (!isObject(data) || data.type !== type) return null;
  if (type === "chat/turn-started") {
    return typeof data.chat_id === "string" ? { type, chat_id: data.chat_id } : null;
  }
  return { type };
}

function handOut(type: AppEventType, message: MessageEvent<string>): void {
  const event = appEventOf(type, JSON.parse(message.data));
  if (event === null) return;
  listeners.forEach((listener) => listener(event));
}

function open(): EventSource {
  const opened = new EventSource(APP_EVENTS_URL);
  APP_EVENT_TYPES.forEach((type) => {
    opened.addEventListener(type, (message) => handOut(type, message));
  });
  return opened;
}

function subscribe(listener: Listener): () => void {
  listeners = [...listeners, listener];
  source ??= open();
  return () => {
    listeners = listeners.filter((other) => other !== listener);
    if (listeners.length > 0) return;
    source?.close();
    source = null;
  };
}

/** Calls `onEvent` with every app event while the calling component is mounted. */
export function useAppEvent(onEvent: (event: AppEvent) => void): void {
  const latest = useRef(onEvent);

  useEffect(() => {
    latest.current = onEvent;
  }, [onEvent]);

  useEffect(() => subscribe((event) => latest.current(event)), []);
}
