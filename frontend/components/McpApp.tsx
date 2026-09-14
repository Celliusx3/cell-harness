"use client";

import { AppBridge, PostMessageTransport } from "@modelcontextprotocol/ext-apps/app-bridge";
import { useEffect, useRef, useState } from "react";

import { ApiError, callAppTool, getAppResource } from "@/lib/api";
import type { ToolItem } from "@/lib/timeline";
import type { ToolUi } from "@/lib/types";

/** What this host calls itself in `ui/initialize`. */
const HOST = { name: "cell-harness", version: "0.1.0" };
/** Before the app reports its own size. */
const INITIAL_HEIGHT = 200;

/**
 * An MCP App: the server's HTML in a sandboxed iframe, speaking the MCP Apps
 * protocol over `postMessage` through the official `AppBridge`.
 *
 * The iframe has no `allow-same-origin`, so it runs on an opaque origin — the
 * spec's requirement that host and app differ — and its Content-Security-Policy
 * is a `<meta>` tag the harness composed from what the resource declared (the
 * default allows inline script and no network). Order matters: the bridge is
 * connected *before* `srcdoc` is set, so the listener is armed before the app's
 * script can send `ui/initialize`; `contentWindow` keeps its identity across
 * that navigation.
 *
 * The effect keys on the app's identity, not the item: the timeline rebuilds
 * every item on every event, and remounting the iframe would restart the app.
 */
export function McpApp({ item, ui }: { item: ToolItem; ui: ToolUi }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const latest = useRef({ item, ui });
  latest.current = { item, ui };
  const [srcdoc, setSrcdoc] = useState<string | null>(null);
  const [height, setHeight] = useState(INITIAL_HEIGHT);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    const iframe = frame.current;
    if (iframe === null || iframe.contentWindow === null) return;
    const bridge = new AppBridge(
      null,
      HOST,
      { serverTools: {}, openLinks: {} },
      {
        hostContext: {
          theme: darkScheme().matches ? "dark" : "light",
          displayMode: "inline",
          platform: "web",
        },
      },
    );
    bridge.oncalltool = async ({ name, arguments: args }) => {
      try {
        // The server's result, verbatim — the app was written against that shape.
        return await callAppTool(ui.server, name, args ?? {}, ui.resource_uri);
      } catch (error: unknown) {
        // MCP-shaped, so the app shows it the way it shows a tool's own error.
        const text = error instanceof ApiError ? error.message : String(error);
        return { content: [{ type: "text", text }], isError: true };
      }
    };
    bridge.onsizechange = ({ height: wanted }) => {
      if (wanted !== undefined) setHeight(Math.ceil(wanted));
    };
    bridge.onopenlink = async ({ url }) => {
      window.open(url, "_blank", "noopener,noreferrer");
      return {};
    };
    bridge.oninitialized = () => {
      const { item: current, ui: bound } = latest.current;
      bridge.sendToolInput({ arguments: parseArguments(current.call.arguments) });
      // `ui` only ever arrives with the result, so the result is here to send.
      void bridge.sendToolResult({
        content: (current.result ?? [])
          .filter((b): b is Extract<typeof b, { type: "text" }> => b.type === "text")
          .map((b) => ({ type: "text", text: b.text })),
        structuredContent: asObject(bound.data),
        isError: current.error !== null,
      });
    };
    const scheme = darkScheme();
    const onScheme = (event: MediaQueryListEvent) => {
      void bridge.sendHostContextChange({ theme: event.matches ? "dark" : "light" });
    };
    scheme.addEventListener("change", onScheme);

    let cancelled = false;
    (async () => {
      try {
        await bridge.connect(new PostMessageTransport(iframe.contentWindow!, iframe.contentWindow!));
        const resource = await getAppResource(ui.server, ui.resource_uri);
        if (!cancelled) setSrcdoc(withPolicy(resource.html, resource.csp));
      } catch (error: unknown) {
        if (!cancelled) setProblem(error instanceof Error ? error.message : String(error));
      }
    })();

    return () => {
      cancelled = true;
      scheme.removeEventListener("change", onScheme);
      void bridge.close();
    };
    // The app's identity, deliberately — see the component docstring.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ui.server, ui.resource_uri]);

  return (
    <div className="border-t border-line bg-surface">
      {problem !== null && <p className="px-3 py-2 text-xs text-danger">app: {problem}</p>}
      <iframe
        ref={frame}
        title={ui.resource_uri}
        sandbox="allow-scripts allow-forms"
        srcDoc={srcdoc ?? undefined}
        className="block w-full border-0"
        style={{ height: `${height}px`, colorScheme: "normal" }}
      />
    </div>
  );
}

function darkScheme(): MediaQueryList {
  return window.matchMedia("(prefers-color-scheme: dark)");
}

/** The policy goes in the document, since a `srcdoc` has no headers. */
function withPolicy(html: string, csp: string): string {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${csp.replace(/"/g, "&quot;")}">`;
  const head = /<head[^>]*>/i.exec(html);
  if (head !== null) {
    const at = head.index + head[0].length;
    return html.slice(0, at) + meta + html.slice(at);
  }
  return meta + html;
}

/** The model's raw argument string, as the object the app is told about. */
function parseArguments(raw: string): Record<string, unknown> {
  try {
    return asObject(JSON.parse(raw)) ?? {};
  } catch {
    return {};
  }
}

function asObject(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}
