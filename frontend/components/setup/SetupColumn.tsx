import type { ReactNode } from "react";

/** The setup screen's column, centred in a window with no sidebar. */
export function SetupColumn({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-w-0 flex-1 flex-col overflow-y-auto px-4 py-10">
      <div className="m-auto w-full max-w-md">{children}</div>
    </main>
  );
}
