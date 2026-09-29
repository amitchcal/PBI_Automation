import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ToastProvider } from "@/components/ui";

export const metadata: Metadata = {
  title: "Meridian Insight Studio",
  description: "From your data to a checked Power BI dashboard, step by step.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0F172A" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
