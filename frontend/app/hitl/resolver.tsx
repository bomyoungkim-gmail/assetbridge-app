"use client";

import { useState } from "react";
import { decidirPendencia, type DecisaoIdentidade } from "@/lib/api";
import { useRouter } from "next/navigation";

// Formulário mínimo de decisão: o operador confirma os campos fortes de
// identidade e cunha o IUP via POST /pending/{id}/decision. A regra de cunho é
// do backend (IupRegistry); este componente só coleta e envia. Restyle ADR-0014.
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
    return (
      <button
        className="btn btn--sm"
        type="button"
        aria-expanded={false}
        aria-controls={`resolver-${pendingId}`}
        onClick={() => setAberto(true)}
      >
        Resolver
      </button>
    );
  }

  return (
    <div
      className="resolver"
      id={`resolver-${pendingId}`}
      role="region"
      aria-label={`Resolver pendência ${pendingId}`}
    >
      <div className="field">
        <label htmlFor={`tipo-${pendingId}`}>Tipo</label>
        <input
          id={`tipo-${pendingId}`}
          type="text"
          value={form.tipo}
          onChange={(e) => campo("tipo", e.target.value)}
          placeholder="CDB / CRI / LF"
          autoComplete="off"
        />
      </div>
      <div className="field">
        <label htmlFor={`venc-${pendingId}`}>Vencimento</label>
        <input
          id={`venc-${pendingId}`}
          type="date"
          value={form.data_vencimento}
          onChange={(e) => campo("data_vencimento", e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor={`isin-${pendingId}`}>ISIN</label>
        <input
          id={`isin-${pendingId}`}
          type="text"
          inputMode="text"
          spellCheck={false}
          autoComplete="off"
          value={form.isin ?? ""}
          onChange={(e) => campo("isin", e.target.value)}
          placeholder="BR0000000000"
        />
        <span className="hint">
          Placeholder <code>BR0000000000</code> conta como nulo.
        </span>
      </div>
      <div className="field">
        <label htmlFor={`cnpj-${pendingId}`}>CNPJ emissor</label>
        <input
          id={`cnpj-${pendingId}`}
          type="text"
          inputMode="numeric"
          spellCheck={false}
          autoComplete="off"
          value={form.cnpj_emissor ?? ""}
          onChange={(e) => campo("cnpj_emissor", e.target.value)}
          placeholder="00.000.000/0001-00"
        />
      </div>
      <div className="field">
        <label htmlFor={`serie-${pendingId}`}>Série</label>
        <input
          id={`serie-${pendingId}`}
          type="text"
          autoComplete="off"
          value={form.serie_emissao ?? ""}
          onChange={(e) => campo("serie_emissao", e.target.value)}
        />
      </div>
      <div className="field check">
        <input
          id={`sub-${pendingId}`}
          type="checkbox"
          checked={form.is_subordinado ?? false}
          onChange={(e) => campo("is_subordinado", e.target.checked)}
        />
        <label htmlFor={`sub-${pendingId}`}>Subordinada</label>
      </div>

      {erro && (
        <p className="msg-erro" role="alert" style={{ gridColumn: "1 / -1" }}>
          {erro}
        </p>
      )}
      <div className="actions">
        <button
          className="btn"
          type="button"
          onClick={() => setAberto(false)}
          disabled={enviando}
        >
          Cancelar
        </button>
        <button
          className="btn btn--primary"
          type="button"
          onClick={submeter}
          disabled={enviando}
        >
          {enviando ? "Cunhando…" : "Cunhar IUP"}
        </button>
      </div>
    </div>
  );
}
