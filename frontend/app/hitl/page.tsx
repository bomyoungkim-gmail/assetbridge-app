import { listarPendencias, type Pendencia } from "@/lib/api";
import Resolver from "./resolver";

// Server Component: busca a fila no backend a cada request (no-store).
// Tela "Fila HITL" + ação "Resolver" do ADR-0009 §5.
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
    <section>
      <h1>Fila HITL</h1>
      <p>
        Pendências aguardando decisão humana. O AssetBridge é a autoridade única
        do IUP — a decisão de cunho mora aqui, nunca no consumidor (ADR-0009).
      </p>

      {erro && (
        <div className="stub">
          Não foi possível carregar a fila: {erro}. Confira{" "}
          <code>ASSETBRIDGE_API_URL</code> e se o backend está no ar.
        </div>
      )}

      {!erro && pendencias.length === 0 && <p>Nenhuma pendência aberta.</p>}

      {pendencias.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Chave provisória</th>
              <th>Motivo</th>
              <th>Payload bruto</th>
              <th>Decisão</th>
            </tr>
          </thead>
          <tbody>
            {pendencias.map((p) => (
              <tr key={p.id}>
                <td>{p.id}</td>
                <td>
                  <code>{p.chave_provisoria}</code>
                </td>
                <td>{p.motivo}</td>
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
      )}
    </section>
  );
}
