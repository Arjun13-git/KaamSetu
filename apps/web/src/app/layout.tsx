import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "KaamSetu",
  description: "Service operations with memory for local businesses.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
