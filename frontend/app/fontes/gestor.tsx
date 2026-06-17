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

  async function remover(id: number) {
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
      <h2>Cadastrar fonte</h2>
      <div style={{ display: "grid", gap: "0.5rem", maxWidth: "32rem" }}>
        <label>
          Nome{" "}
          <input
            value={form.nome}
            onChange={(e) => campo("nome", e.target.value)}
            placeholder="B3 instrumentos"
          />
        </label>
        <label>
          Tipo{" "}
          <select
            value={form.tipo}
            onChange={(e) => campo("tipo", e.target.value)}
          >
            <option value="api">api (liga vivo)</option>
            <option value="csv">csv (deferido)</option>
            <option value="scraping">scraping (deferido)</option>
          </select>
        </label>
        <label>
          Base URL{" "}
          <input
            value={form.base_url ?? ""}
            onChange={(e) => campo("base_url", e.target.value)}
            placeholder="https://api.exemplo.gov.br"
          />
        </label>
        <label>
          Path{" "}
          <input
            value={form.path ?? ""}
            onChange={(e) => campo("path", e.target.value)}
            placeholder="/instrumento"
          />
        </label>
        <label>
          Parâmetro de consulta{" "}
          <input
            value={form.param ?? "isin"}
            onChange={(e) => campo("param", e.target.value)}
            placeholder="isin"
          />
        </label>
        <label>
          field_map (JSON: coluna_da_fonte → característica)
          <textarea
            value={fieldMapTxt}
            onChange={(e) => setFieldMapTxt(e.target.value)}
            placeholder={'{ "setor": "setor", "nome_longo": "nome_longo" }'}
            rows={3}
          />
        </label>
        {erro && <p style={{ color: "#b00" }}>{erro}</p>}
        <button onClick={submeter} disabled={enviando || !form.nome}>
          {enviando ? "Cadastrando…" : "Cadastrar fonte"}
        </button>
      </div>

      <h2 style={{ marginTop: "1.5rem" }}>Fontes cadastradas</h2>
      {fontesIniciais.length === 0 ? (
        <p>Nenhuma fonte cadastrada.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Nome</th>
              <th>Tipo</th>
              <th>Base URL</th>
              <th>Estado</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {fontesIniciais.map((f) => (
              <tr key={f.id}>
                <td>{f.nome}</td>
                <td>{f.tipo}</td>
                <td>
                  <code style={{ fontSize: "0.75rem" }}>{f.base_url ?? "—"}</code>
                </td>
                <td>
                  {f.vivo ? "🟢 viva" : f.enabled ? "⚪ deferida" : "⏸️ desligada"}
                </td>
                <td>
                  <button onClick={() => toggle(f)}>
                    {f.enabled ? "Desligar" : "Ligar"}
                  </button>{" "}
                  <button onClick={() => remover(f.id)}>Remover</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
