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
// catálogo (/assets, /positions, /imports). Restyle ADR-0014.
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
    <section aria-labelledby="h-acervo">
      <div className="page-head">
        <div>
          <h1 id="h-acervo">Acervo</h1>
          <p>
            O que já foi injetado no AssetBridge: imports na landing zone (bruto
            imutável), projeção de posição (direção a) e IUPs cunhados
            (autoridade do registro). Read-only.
          </p>
        </div>
      </div>

      {erro && (
        <div className="stub" role="alert">
          Não foi possível carregar o acervo: {erro}. Confira{" "}
          <code>ASSETBRIDGE_API_URL</code> e se o backend está no ar.
        </div>
      )}

      <div className="panel">
        <header>
          <h2>Enviar import</h2>
        </header>
        <div style={{ padding: "1rem" }}>
          <Uploader />
        </div>
      </div>

      <div className="panel">
        <header>
          <h2>Imports (landing zone) — {totais.imports}</h2>
        </header>
        {imports.length === 0 ? (
          <div className="empty">
            <strong>Nenhum import ainda</strong>
            Envie um XML BTG acima para popular a landing zone.
          </div>
        ) : (
          <table>
            <caption className="sr-only">Imports na landing zone</caption>
            <thead>
              <tr>
                <th className="num" scope="col">
                  ID
                </th>
                <th scope="col">Custodiante</th>
                <th scope="col">Content hash</th>
                <th className="num" scope="col">
                  Bytes
                </th>
                <th scope="col">Quando</th>
              </tr>
            </thead>
            <tbody>
              {imports.map((i) => (
                <tr key={i.id}>
                  <td className="num">{i.id}</td>
                  <td>{i.custodiante}</td>
                  <td>
                    <code title={i.content_hash}>
                      {i.content_hash.slice(0, 16)}…
                    </code>
                  </td>
                  <td className="num">{i.tamanho_bytes}</td>
                  <td>{i.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <header>
          <h2>Posições — {totais.posicoes}</h2>
        </header>
        {posicoes.length === 0 ? (
          <div className="empty">
            <strong>Nenhuma posição projetada</strong>
            Posições aparecem após um import ser processado (direção a).
          </div>
        ) : (
          <table>
            <caption className="sr-only">Projeção de posições</caption>
            <thead>
              <tr>
                <th scope="col">Carteira</th>
                <th scope="col">Custodiante</th>
                <th scope="col">IUP</th>
                <th scope="col">asof</th>
                <th className="num" scope="col">
                  Qtd
                </th>
                <th className="num" scope="col">
                  PU
                </th>
              </tr>
            </thead>
            <tbody>
              {posicoes.map((p) => (
                <tr key={p.id}>
                  <td>{p.id_carteira}</td>
                  <td>{p.custodiante}</td>
                  <td>
                    {p.iup ? (
                      <code className="truncate" title={p.iup}>
                        {p.iup}
                      </code>
                    ) : (
                      <span className="badge badge--warn">pendente (HITL)</span>
                    )}
                  </td>
                  <td>{p.asof}</td>
                  <td className="num">{p.quantidade}</td>
                  <td className="num">{p.pu ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <header>
          <h2>IUPs cunhados — {totais.ativos}</h2>
        </header>
        {ativos.length === 0 ? (
          <div className="empty">
            <strong>Nenhum IUP cunhado</strong>
            IUPs são cunhados ao resolver identidade (chave forte ou via HITL).
          </div>
        ) : (
          <table>
            <caption className="sr-only">IUPs cunhados no registro</caption>
            <thead>
              <tr>
                <th className="num" scope="col">
                  ID
                </th>
                <th scope="col">IUP</th>
                <th scope="col">Chave sintética</th>
                <th scope="col">Quando</th>
              </tr>
            </thead>
            <tbody>
              {ativos.map((a) => (
                <tr key={a.id}>
                  <td className="num">{a.id}</td>
                  <td>
                    <code className="truncate" title={a.iup}>
                      {a.iup}
                    </code>
                  </td>
                  <td>
                    <code
                      className="truncate"
                      title={a.chave_sintetica ?? "NULL (HITL)"}
                    >
                      {a.chave_sintetica ?? "NULL (HITL)"}
                    </code>
                  </td>
                  <td>{a.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
