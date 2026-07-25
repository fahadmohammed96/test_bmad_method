import type { Metadata } from "next";
import { appCopy } from "@/lib/copy/app";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: appCopy.nome,
  description: appCopy.descrizione,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="it">
      <body className="bg-surface text-surface-contrast font-body antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
