import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { RunProvider } from "../lib/runStore";
import { TopNav } from "../components/nav/TopNav";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Variant Studio",
  description: "Local zero-config video variant studio",
};

// Prevent static HTML shells from being cached by RunPod's CDN with stale JS refs.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-bg text-text">
        <RunProvider>
          <TopNav />
          {children}
        </RunProvider>
      </body>
    </html>
  );
}
