import "./globals.css";
import type { Metadata } from "next";
export const metadata: Metadata = { title: "SwasthyaSetu", description: "AI-assisted rural healthcare triage" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
