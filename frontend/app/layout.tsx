import type { Metadata } from "next";
import { Inter, Source_Serif_4 } from "next/font/google";

import "./globals.css";

const sans = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });
const serif = Source_Serif_4({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-source-serif",
});

export const metadata: Metadata = {
  title: "cell-harness",
  description: "An agent harness you can talk to.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable}`}>
      <body className="flex h-full">{children}</body>
    </html>
  );
}
