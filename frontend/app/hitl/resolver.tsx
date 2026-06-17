"use client";

import { useState } from "react";
import { decidirPendencia, type DecisaoIdentidade } from "@/lib/api";
import { useRouter } from "next/navigation";

// Formulário mínimo de decisão: o operador confirma os campos fortes de
// identidade e cunha o IUP via POST /pending/{id}/decision. A regra de cunho é
// do backend (IupRegistry); este componente só coleta e envia.
export default function Resolver({ pendingId }: { pendingId: number }) {
  const router = useRouter();
  const [aberto, setAberto] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [form, setForm] = useState<DecisaoIdentidade>({
    tipo: "",
    data_vencimento: "",
    isin: "",
    cnpj_emissor: "",
    serie_emissao: "",
    is_subordinado: false,
  });

  function campo(nome: keyof DecisaoIdentidade, valor: string | boolean) {
    setForm((f) => ({ ...f, [nome]: valor }));
  }

  async function submeter() {
    setEnviando(true);
    setErro(null);
    try {
      await decidirPendencia(pendingId, form);
      setAberto(false);
      router.refresh(); // recarrega a fila — pendência sai da lista
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  if (!aberto) {
    return <button onClick={() => setAberto(true)}>Resolver</button>;
  }

  return (
    <div>
      <label>
        Tipo{" "}
        <input
          value={form.tipo}
          onChange={(e) => campo("tipo", e.target.value)}
          placeholder="CDB / CRI / LF"
        />
      </label>
      <br />
      <label>
        Vencimento{" "}
        <input
          value={form.data_vencimento}
          onChange={(e) => campo("data_vencimento", e.target.value)}
          placeholder="YYYY-MM-DD"
        />
      </label>
      <br />
      <label>
        ISIN{" "}
        <input
          value={form.isin ?? ""}
          onChange={(e) => campo("isin", e.target.value)}
        />
      </label>
      <br />
      <label>
        CNPJ emissor{" "}
        <input
          value={form.cnpj_emissor ?? ""}
          onChange={(e) => campo("cnpj_emissor", e.target.value)}
        />
      </label>
      <br />
      <label>
        Série{" "}
        <input
          value={form.serie_emissao ?? ""}
          onChange={(e) => campo("serie_emissao", e.target.value)}
        />
      </label>
      <br />
      <label>
        <input
          type="checkbox"
          checked={form.is_subordinado ?? false}
          onChange={(e) => campo("is_subordinado", e.target.checked)}
        />{" "}
        Subordinada
      </label>
      <br />
      {erro && <p style={{ color: "#b00" }}>{erro}</p>}
      <button onClick={submeter} disabled={enviando}>
        {enviando ? "Cunhando…" : "Cunhar IUP"}
      </button>{" "}
      <button onClick={() => setAberto(false)} disabled={enviando}>
        Cancelar
      </button>
    </div>
  );
}
