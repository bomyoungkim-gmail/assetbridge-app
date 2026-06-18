import type { Metadata } from "next";
import "./globals.css";
import Nav from "./nav";

export const metadata: Metadata = {
  title: "AssetBridge — Backoffice HITL",
  description: "Resolução humana de ambiguidade de IUP (ADR-0009).",
};

// Shell do backoffice (ADR-0014): sidebar fixa + skip link + topbar. O item
// ativo da navegação vive no client component Nav (aria-current via usePathname).
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" translate="no">
      <body>
        <a className="skip" href="#main">
          Pular para o conteúdo
        </a>
        <div className="app">
          <aside className="sidebar" aria-label="Navegação principal">
            <div className="brand">
              <span className="dot" aria-hidden="true" /> AssetBridge
            </div>
            <Nav />
            <div className="sidebar-foot">Autoridade do IUP · backoffice interno</div>
          </aside>
          <div className="main">
            <main className="content" id="main">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
