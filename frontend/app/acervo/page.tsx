import {
  listarAtivos,
  listarPosicoes,
  listarImports,
  type Ativo,
  type Posicao,
  type Import,
} from "@/lib/api";
import Uploader from "./uploader";

// Acervo (item 4 / browse): o que já foi injetado. Server Component, read-only
// — busca no backend a cada request (no-store). Espelha os endpoints de
// catálogo (/assets, /positions, /imports). Visibilidade operacional enquanto
// não há tela rica (ADR-0009 §5).
export default async function AcervoPage() {
  let ativos: Ativo[] = [];
  let posicoes: Posicao[] = [];
  let imports: Import[] = [];
  let totais = { ativos: 0, posicoes: 0, imports: 0 };
  let erro: string | null = null;

  try {
    const [a, p, i] = await Promise.all([
      listarAtivos(),
      listarPosicoes(),
      listarImports(),
    ]);
    ativos = a.itens;
    posicoes = p.itens;
    imports = i.itens;
    totais = { ativos: a.total, posicoes: p.total, imports: i.total };
  } catch (e) {
    erro = e instanceof Error ? e.message : String(e);
  }

  return (
    <section>
      <h1>Acervo</h1>
      <p>
        O que já foi injetado no AssetBridge: imports na landing zone (bruto
        imutável), projeção de posição (direção a) e IUPs cunhados (autoridade do
        registro). Read-only.
      </p>

      {erro && (
        <div className="stub">
          Não foi possível carregar o acervo: {erro}. Confira{" "}
          <code>ASSETBRIDGE_API_URL</code> e se o backend está no ar.
        </div>
      )}

      <h2>Enviar import</h2>
      <Uploader />

      <h2 style={{ marginTop: "1.5rem" }}>Imports (landing zone) — {totais.imports}</h2>
      {imports.length === 0 ? (
        <p>Nenhum import ainda. Envie um XML BTG acima.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Custodiante</th>
              <th>Content hash</th>
              <th>Bytes</th>
              <th>Quando</th>
            </tr>
          </thead>
          <tbody>
            {imports.map((i) => (
              <tr key={i.id}>
                <td>{i.id}</td>
                <td>{i.custodiante}</td>
                <td>
                  <code style={{ fontSize: "0.75rem" }}>
                    {i.content_hash.slice(0, 16)}…
                  </code>
                </td>
                <td>{i.tamanho_bytes}</td>
                <td>{i.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2 style={{ marginTop: "1.5rem" }}>Posições — {totais.posicoes}</h2>
      {posicoes.length === 0 ? (
        <p>Nenhuma posição projetada ainda.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Carteira</th>
              <th>Custodiante</th>
              <th>IUP</th>
              <th>asof</th>
              <th>Qtd</th>
              <th>PU</th>
            </tr>
          </thead>
          <tbody>
            {posicoes.map((p) => (
              <tr key={p.id}>
                <td>{p.id_carteira}</td>
                <td>{p.custodiante}</td>
                <td>
                  {p.iup ? (
                    <code style={{ fontSize: "0.75rem" }}>{p.iup}</code>
                  ) : (
                    <em>pendente (HITL)</em>
                  )}
                </td>
                <td>{p.asof}</td>
                <td>{p.quantidade}</td>
                <td>{p.pu ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2 style={{ marginTop: "1.5rem" }}>IUPs cunhados — {totais.ativos}</h2>
      {ativos.length === 0 ? (
        <p>Nenhum IUP cunhado ainda.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>IUP</th>
              <th>Chave sintética</th>
              <th>Quando</th>
            </tr>
          </thead>
          <tbody>
            {ativos.map((a) => (
              <tr key={a.id}>
                <td>{a.id}</td>
                <td>
                  <code style={{ fontSize: "0.75rem" }}>{a.iup}</code>
                </td>
                <td>
                  <code style={{ fontSize: "0.75rem" }}>
                    {a.chave_sintetica ?? "NULL (HITL)"}
                  </code>
                </td>
                <td>{a.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
