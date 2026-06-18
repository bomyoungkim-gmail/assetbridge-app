"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  criarFonte,
  removerFonte,
  alterarFonte,
  type Fonte,
  type NovaFonte,
} from "@/lib/api";

const VAZIA: NovaFonte = {
  nome: "",
  tipo: "api",
  base_url: "",
  path: "",
  param: "isin",
  confianca: 0.9,
};

// Cliente fino do registry de fontes (ADR-0011): coleta o cadastro e chama o
// backend. Nenhuma regra de domínio aqui; `field_map` é JSON livre (o contrato
// real do endpoint da fonte é config). `tipo='api'` é o que liga vivo no grafo.
// Restyle ADR-0014.
export default function GestorFontes({
  fontesIniciais,
}: {
  fontesIniciais: Fonte[];
}) {
  const router = useRouter();
  const [form, setForm] = useState<NovaFonte>(VAZIA);
  const [fieldMapTxt, setFieldMapTxt] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  function campo(nome: keyof NovaFonte, valor: string | number) {
    setForm((f) => ({ ...f, [nome]: valor }));
  }

  async function submeter() {
    setEnviando(true);
    setErro(null);
    try {
      let field_map: Record<string, string> | null = null;
      if (fieldMapTxt.trim()) {
        field_map = JSON.parse(fieldMapTxt) as Record<string, string>;
      }
      await criarFonte({ ...form, field_map });
      setForm(VAZIA);
      setFieldMapTxt("");
      router.refresh();
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  async function remover(id: number, nome: string) {
    // Ação destrutiva — confirma antes (guideline).
    if (!window.confirm(`Remover a fonte "${nome}"? Esta ação não pode ser desfeita.`)) {
      return;
    }
    setErro(null);
    try {
      await removerFonte(id);
      router.refresh();
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    }
  }

  async function toggle(f: Fonte) {
    setErro(null);
    try {
      await alterarFonte(f.id, !f.enabled);
      router.refresh();
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div>
      <div className="panel">
        <header>
          <h2>Cadastrar fonte</h2>
        </header>
        <div className="form-grid" style={{ padding: "1rem" }}>
          <div className="field">
            <label htmlFor="f-nome">Nome</label>
            <input
              id="f-nome"
              type="text"
              value={form.nome}
              onChange={(e) => campo("nome", e.target.value)}
              placeholder="B3 instrumentos"
              autoComplete="off"
            />
          </div>
          <div className="field">
            <label htmlFor="f-tipo">Tipo</label>
            <select
              id="f-tipo"
              value={form.tipo}
              onChange={(e) => campo("tipo", e.target.value)}
            >
              <option value="api">api (liga vivo)</option>
              <option value="csv">csv (deferido)</option>
              <option value="scraping">scraping (deferido)</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-base">Base URL</label>
            <input
              id="f-base"
              type="text"
              inputMode="url"
              spellCheck={false}
              autoComplete="off"
              value={form.base_url ?? ""}
              onChange={(e) => campo("base_url", e.target.value)}
              placeholder="https://api.exemplo.gov.br"
            />
          </div>
          <div className="field">
            <label htmlFor="f-path">Path</label>
            <input
              id="f-path"
              type="text"
              spellCheck={false}
              autoComplete="off"
              value={form.path ?? ""}
              onChange={(e) => campo("path", e.target.value)}
              placeholder="/instrumento"
            />
          </div>
          <div className="field">
            <label htmlFor="f-param">Parâmetro de consulta</label>
            <input
              id="f-param"
              type="text"
              spellCheck={false}
              autoComplete="off"
              value={form.param ?? "isin"}
              onChange={(e) => campo("param", e.target.value)}
              placeholder="isin"
            />
          </div>
          <div className="field">
            <label htmlFor="f-map">
              field_map (JSON: coluna_da_fonte → característica)
            </label>
            <textarea
              id="f-map"
              value={fieldMapTxt}
              onChange={(e) => setFieldMapTxt(e.target.value)}
              placeholder={'{ "setor": "setor", "nome_longo": "nome_longo" }'}
              rows={3}
              spellCheck={false}
            />
          </div>
          {erro && (
            <p className="msg-erro" role="alert">
              {erro}
            </p>
          )}
          <button
            className="btn btn--primary"
            type="button"
            onClick={submeter}
            disabled={enviando || !form.nome}
          >
            {enviando ? "Cadastrando…" : "Cadastrar fonte"}
          </button>
        </div>
      </div>

      <div className="panel">
        <header>
          <h2>Fontes cadastradas — {fontesIniciais.length}</h2>
        </header>
        {fontesIniciais.length === 0 ? (
          <div className="empty">
            <strong>Nenhuma fonte cadastrada</strong>
            Cadastre uma fonte-<code>api</code> acima para ligá-la viva no grafo.
          </div>
        ) : (
          <table>
            <caption className="sr-only">Fontes de enriquecimento</caption>
            <thead>
              <tr>
                <th scope="col">Nome</th>
                <th scope="col">Tipo</th>
                <th scope="col">Base URL</th>
                <th scope="col">Estado</th>
                <th scope="col">
                  <span className="sr-only">Ações</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {fontesIniciais.map((f) => (
                <tr key={f.id}>
                  <td>{f.nome}</td>
                  <td>
                    <span className="badge badge--muted">{f.tipo}</span>
                  </td>
                  <td>
                    <code className="truncate" title={f.base_url ?? "—"}>
                      {f.base_url ?? "—"}
                    </code>
                  </td>
                  <td>
                    {f.vivo ? (
                      <span className="badge badge--ok">Viva</span>
                    ) : f.enabled ? (
                      <span className="badge badge--warn">Deferida</span>
                    ) : (
                      <span className="badge badge--muted">Desligada</span>
                    )}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      <button
                        className="btn btn--sm"
                        type="button"
                        onClick={() => toggle(f)}
                      >
                        {f.enabled ? "Desligar" : "Ligar"}
                      </button>
                      <button
                        className="btn btn--sm btn--danger"
                        type="button"
                        onClick={() => remover(f.id, f.nome)}
                      >
                        Remover
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
