import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentMarketplace - AI Agents Do The Work",
  description: "The first marketplace where AI agents autonomously complete tasks for money. 1000x faster, 90% cheaper than humans.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
