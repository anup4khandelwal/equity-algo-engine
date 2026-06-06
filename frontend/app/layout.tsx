import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "equity-algo-engine — dashboard",
  description: "Read-only monitoring for the paper-trading engine",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
