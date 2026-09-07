"use client";

import { Check, Copy } from "lucide-react";
import { Highlight } from "prism-react-renderer";
import { memo, useEffect, useState } from "react";

/**
 * Highlighted, scrollable, copyable source.
 *
 * `Highlight` defaults to its own `vsDark` theme and emits inline styles, which
 * CSS cannot reach. Handing it an empty theme leaves bare `token <type>` classes
 * instead, so the palette lives in `globals.css` and flips with the OS theme —
 * no `matchMedia`, no hydration guard, nothing read from the browser at render.
 *
 * Memoized because `Timeline` reallocates every item on every stream event, so
 * without it each finished block would re-tokenize once per chunk of whatever is
 * currently arriving.
 */
const NO_THEME = { plain: {}, styles: [] };

export const CodeBlock = memo(function CodeBlock({
  code,
  language,
  className,
}: {
  code: string;
  language: string;
  className: string;
}) {
  return (
    <div className="relative">
      <CopyButton code={code} />
      <Highlight theme={NO_THEME} code={code} language={language}>
        {({ tokens, getLineProps, getTokenProps }) => (
          <pre
            className={`max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg p-2 pr-9 font-mono text-xs ${className}`}
          >
            {tokens.map((line, index) => (
              <div key={index} {...getLineProps({ line })}>
                {line.map((token, at) => (
                  <span key={at} {...getTokenProps({ token })} />
                ))}
              </div>
            ))}
          </pre>
        )}
      </Highlight>
    </div>
  );
});

/**
 * Outside the `<pre>` on purpose: inside a `max-h-96 overflow-auto` box it would
 * scroll out of reach on exactly the long program worth copying.
 */
function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy() {
    // Undefined outside a secure context, which this harness meets the moment
    // someone opens it over the LAN. Failing silently leaves the icon unchanged.
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      return;
    }
  }

  return (
    <button
      onClick={copy}
      aria-label={copied ? "Copied" : "Copy code"}
      className="absolute right-1.5 top-1.5 z-10 rounded-md border border-line bg-surface-sunken p-1 text-ink-soft transition-colors hover:text-ink"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
    </button>
  );
}
