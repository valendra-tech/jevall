import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Jevall Snake",
  description:
    "Snake controlled one probabilistic decision at a time through a typed-decision API.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-full antialiased">{children}</body>
    </html>
  );
}
