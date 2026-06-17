import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AssetBridge — Backoffice HITL",
  description: "Resolução humana de ambiguidade de IUP (ADR-0009).",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body>
        <header className="topbar">
          <strong>AssetBridge</strong>
          <nav>
            <Link href="/">Painel</Link>
            <Link href="/hitl">Fila HITL</Link>
            <Link href="/acervo">Acervo</Link>
            <Link href="/fontes">Fontes</Link>
          </nav>
        </header>
        <main className="content">{children}</main>
      </body>
    </html>
  );
}
