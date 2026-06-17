// Painel — stub consciente (ADR-0009 §5). NÃO há endpoint de métricas no
// backend ainda; não simulamos números como se prontos. Vira tela real quando
// o backend expuser volume/taxa de ambiguidade/threads pausadas.
export default function PainelPage() {
  return (
    <section>
      <h1>Painel</h1>
      <div className="stub">
        <strong>Em construção.</strong> Métricas (volume processado, taxa de
        ambiguidade, threads pausadas) dependem de um endpoint de métricas que o
        backend ainda não expõe. Ver ADR-0009 §5 e o item &ldquo;Fase de UI&rdquo;
        no CONTEXT.md.
      </div>
      <p style={{ marginTop: "1rem" }}>
        Operacional disponível hoje: <a href="/hitl">Fila HITL</a> (lastreada por{" "}
        <code>GET /pending</code> e <code>POST /pending/&#123;id&#125;/decision</code>).
      </p>
    </section>
  );
}
