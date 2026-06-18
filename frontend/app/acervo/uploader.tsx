"use client";

import { useRef, useState } from "react";
import { enviarIngest } from "@/lib/api";
import { useRouter } from "next/navigation";

// Upload de XML BTG para a landing zone (POST /ingest). Só transporta o arquivo;
// parse e cunho de IUP são do backend. Ao concluir, recarrega o acervo para a
// nova posição/import aparecer. Restyle ADR-0014.
export default function Uploader() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function enviar() {
    if (!file) {
      setErro("Escolha um XML BTG primeiro.");
      return;
    }
    setEnviando(true);
    setErro(null);
    setOk(null);
    try {
      const r = await enviarIngest(file);
      setOk(
        r.status === "duplicate"
          ? `Já importado antes (no-op): ${r.file_name ?? file.name}`
          : `Importado: carteira ${r.id_carteira} @ ${r.asof} — ` +
              `${r.posicoes} posição(ões), ${r.pendencias} pendência(s) HITL, ` +
              `${r.excluidos} excluída(s)`,
      );
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      router.refresh();
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="field" style={{ maxWidth: "32rem" }}>
      <label htmlFor="upload-btg">XML BTG</label>
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <input
          id="upload-btg"
          ref={inputRef}
          type="file"
          accept=".xml,text/xml,application/xml"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button
          className="btn btn--primary"
          type="button"
          onClick={enviar}
          disabled={enviando}
        >
          {enviando ? "Enviando…" : "Enviar"}
        </button>
      </div>
      <span className="hint">
        O front é só transporte — o parse &amp; cunho do IUP rodam no backend.
      </span>
      {erro && (
        <p className="msg-erro" role="alert">
          {erro}
        </p>
      )}
      {ok && (
        <p className="msg-ok" aria-live="polite">
          {ok}
        </p>
      )}
    </div>
  );
}
