import { listarPendencias, type Pendencia } from "@/lib/api";
import Resolver from "./resolver";

// Server Component: busca a fila no backend a cada request (no-store).
// Tela "Fila HITL" + ação "Resolver" do ADR-0009 §5. Restyle ADR-0014.
export default async function FilaHitlPage() {
  let pendencias: Pendencia[];
  let erro: string | null = null;
  try {
    pendencias = await listarPendencias();
  } catch (e) {
    erro = e instanceof Error ? e.message : String(e);
    pendencias = [];
  }

  return (
    <section aria-labelledby="h-hitl">
      <div className="page-head">
        <div>
          <h1 id="h-hitl">Fila HITL</h1>
          <p>
            Pendências aguardando decisão humana. O AssetBridge é a autoridade
            única do IUP — a decisão de cunho mora aqui, nunca no consumidor
            (ADR-0009). Nada decide identidade por timeout.
          </p>
        </div>
        {!erro && (
          <span className="badge badge--warn" aria-live="polite">
            {pendencias.length} pendência{pendencias.length === 1 ? "" : "s"}
          </span>
        )}
      </div>

      {erro && (
        <div className="stub" role="alert">
          Não foi possível carregar a fila: {erro}. Confira{" "}
          <code>ASSETBRIDGE_API_URL</code> e se o backend está no ar.
        </div>
      )}

      {!erro && pendencias.length === 0 && (
        <div className="panel">
          <div className="empty">
            <strong>Fila vazia</strong>
            Nenhuma pendência aberta. Ativos sem chave forte aparecem aqui.
          </div>
        </div>
      )}

      {pendencias.length > 0 && (
        <div className="panel">
          <table>
            <caption className="sr-only">
              Pendências de resolução de identidade
            </caption>
            <thead>
              <tr>
                <th className="num" scope="col">
                  #
                </th>
                <th scope="col">Chave provisória</th>
                <th scope="col">Motivo</th>
                <th scope="col">Payload bruto</th>
                <th scope="col">
                  <span className="sr-only">Decisão</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {pendencias.map((p) => (
                <tr key={p.id}>
                  <td className="num">{p.id}</td>
                  <td>
                    <code className="truncate" title={p.chave_provisoria}>
                      {p.chave_provisoria}
                    </code>
                  </td>
                  <td>
                    <span className="badge badge--warn">{p.motivo}</span>
                  </td>
                  <td>
                    <pre style={{ margin: 0, fontSize: "0.8rem" }}>
                      {JSON.stringify(p.payload, null, 2)}
                    </pre>
                  </td>
                  <td>
                    <Resolver pendingId={p.id} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
