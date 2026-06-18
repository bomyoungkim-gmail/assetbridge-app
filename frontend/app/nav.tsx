"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Navegação lateral com item ativo (ADR-0014 §3). Client fino só para marcar
// aria-current="page" via usePathname — nenhuma lógica de domínio.
const ITENS = [
  { href: "/", rotulo: "Painel" },
  { href: "/hitl", rotulo: "Fila HITL" },
  { href: "/acervo", rotulo: "Acervo" },
  { href: "/fontes", rotulo: "Fontes" },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav className="nav" aria-label="Seções">
      {ITENS.map(({ href, rotulo }) => {
        const ativo =
          href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={ativo ? "page" : undefined}
          >
            {rotulo}
          </Link>
        );
      })}
    </nav>
  );
}
