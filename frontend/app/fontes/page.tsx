import { listarFontes, type Fonte } from "@/lib/api";
import GestorFontes from "./gestor";

// Fontes (item 3): registry de fontes de enriquecimento (ADR-0011). Server
// Component lista o catálogo; o cadastro/remoção/toggle é client (GestorFontes).
// Cadastro de fonte-`api` liga vivo no grafo sem mexer em env/código; csv/
// scraping ficam catalogados com execução deferida (ADR-0010). Restyle ADR-0014.
export default async function FontesPage() {
  let fontes: Fonte[] = [];
  let erro: string | null = null;
  try {
    fontes = await listarFontes();
  } catch (e) {
    erro = e instanceof Error ? e.message : String(e);
  }

  return (
    <section aria-labelledby="h-fontes">
      <div className="page-head">
        <div>
          <h1 id="h-fontes">Fontes de enriquecimento</h1>
          <p>
            De onde o AssetBridge puxa características de ativos já identificados
            (emissor, securitizadora, lastro, rating, indexador). Nunca toca
            identidade — só enriquece (ADR-0010). Cadastre uma fonte-
            <code>api</code> e ela liga no grafo na hora; <code>csv</code>/
            <code>scraping</code> ficam catalogados com execução deferida.
          </p>
        </div>
      </div>

      {erro && (
        <div className="stub" role="alert">
          Não foi possível carregar as fontes: {erro}. Confira{" "}
          <code>ASSETBRIDGE_API_URL</code> e se o backend está no ar.
        </div>
      )}

      <GestorFontes fontesIniciais={fontes} />
    </section>
  );
}
