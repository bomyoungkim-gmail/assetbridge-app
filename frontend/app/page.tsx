import Link from "next/link";

// Painel — stub consciente (ADR-0009 §5). NÃO há endpoint de métricas no
// backend ainda; não simulamos números como se prontos. O restyle (ADR-0014) é
// só visual — vira tela real quando o backend expuser volume/ambiguidade/threads.
export default function PainelPage() {
  return (
    <section aria-labelledby="h-painel">
      <div className="page-head">
        <div>
          <h1 id="h-painel">Painel</h1>
          <p>
            Visão operacional do pipeline. As métricas (volume processado, taxa
            de ambiguidade, threads pausadas) dependem de um endpoint que o
            backend ainda não expõe — ver ADR-0009 §5.
          </p>
        </div>
        <span className="badge badge--muted">Aguardando endpoint de métricas</span>
      </div>

      <div className="stub">
        <strong>Em construção.</strong> O Painel não exibe números fabricados:
        enquanto não houver endpoint de métricas, o operacional disponível é a{" "}
        <Link href="/hitl">Fila HITL</Link> (lastreada por <code>GET /pending</code>{" "}
        e <code>POST /pending/&#123;id&#125;/decision</code>) e o{" "}
        <Link href="/acervo">Acervo</Link> (read-only do que foi injetado).
      </div>
    </section>
  );
}
