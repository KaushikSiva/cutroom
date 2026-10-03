import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Geist, Geist_Mono, Newsreader } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const display = Bricolage_Grotesque({ variable: "--font-display", subsets: ["latin"], weight: ["600", "700", "800"] });
const serif = Newsreader({ variable: "--font-serif", subsets: ["latin"], style: ["italic"], weight: ["400"] });

export const metadata: Metadata = {
  title: "Cutroom — a film studio your agents can hire",
  description:
    "Brief it like a director. Claude Code plans, shoots, scores, cuts, captions and critiques a finished film, with every Creative Commons source credited.",
};

export const viewport: Viewport = { themeColor: "#f5f5f2" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} ${display.variable} ${serif.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
