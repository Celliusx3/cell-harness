import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "cell-harness",
  description: "An agent harness you can talk to.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex h-full">{children}</body>
    </html>
  );
}
