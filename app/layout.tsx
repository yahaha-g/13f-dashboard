import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "13F Dashboard",
  description: "Institutional 13F behavior overview",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen max-w-[1280px] mx-auto px-6 py-6">
        {children}
      </body>
    </html>
  );
}
