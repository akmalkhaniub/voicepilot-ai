import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VoicePilot AI | Real-Time Enterprise Voice Assistant",
  description: "Ultra-low latency full-duplex conversational voice AI with AudioWorklet & Silero VAD",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#090d16] text-slate-100 antialiased selection:bg-cyan-500 selection:text-black">
        {children}
      </body>
    </html>
  );
}
