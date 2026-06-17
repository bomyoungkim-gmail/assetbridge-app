from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from .extraction import STRONG_FIELDS, FieldProposal

# Prompt de extração fuzzy. Genérico de propósito: a calibração por custodiante
# (few-shot, regras de classe) é deferida até haver amostra real (ADR-0002).
_PROMPT = (
    "Você extrai metadados de um ativo de renda fixa privada a partir de uma "
    "descrição em português, possivelmente caótica. Preencha SÓ o que tiver "
    "certeza; deixe nulo o que não souber. NUNCA invente CNPJ, ISIN ou datas — "
    "esses não são sua tarefa.\n\nDescrição:\n{raw}"
)

# Default do modelo Ollama p/ uso programático/teste. A fonte de verdade em
# runtime é a env `ASSETBRIDGE_OLLAMA_MODEL` (gate em `hitl._field_proposer`);
# este constante só vale quando se chama o proposer direto sem passar `modelo`.
DEFAULT_OLLAMA_MODEL = "qwen3:8b"  # por enquanto; alvo eventual qwen3:14b (ADR-0013/0014)


class FuzzyExtraction(BaseModel):
    """Saída estruturada do LLM — campos FUZZY apenas (classe/série/subordinação).

    Campos FORTES (CNPJ/ISIN/data) ficam fora de propósito: o LLM nunca os toca
    (ADR-0007); eles saem de regex determinístico em `extraction.py`."""

    tipo: Optional[str] = None  # classe (CRI/CRA/CDB/LF...)
    serie_emissao: Optional[str] = None
    subordinacao: Optional[str] = None  # "SUB" | "SENIOR"


class OllamaProposer:
    """Adapter `FieldProposer` sobre um ChatModel com saída estruturada (Ollama).

    Recebe o modelo já estruturado (`.with_structured_output(FuzzyExtraction)`)
    p/ ser testável sem Ollama no loop. Marca cada proposta com `modelo`
    (extração versionada, ADR-0007). Confiança ainda não-calibrada (deferida até
    dado rotulado) — default conservador."""

    def __init__(self, structured_model, modelo: str = DEFAULT_OLLAMA_MODEL, confianca: float = 0.5):
        self._model = structured_model
        self._modelo = modelo
        self._confianca = confianca

    def propor(self, raw: str) -> list[FieldProposal]:
        out: FuzzyExtraction = self._model.invoke(_PROMPT.format(raw=raw))
        pares = {
            "tipo": out.tipo,
            "serie_emissao": out.serie_emissao,
            "is_subordinado": out.subordinacao,
        }
        return [
            FieldProposal(
                campo=campo,
                valor=str(valor),
                confianca=self._confianca,
                modelo=self._modelo,
            )
            for campo, valor in pares.items()
            if valor and campo not in STRONG_FIELDS
        ]


def build_ollama_proposer(
    modelo: str = DEFAULT_OLLAMA_MODEL, base_url: Optional[str] = None
) -> OllamaProposer:
    """Factory do proposer real (Ollama). Lazy: importa `langchain_ollama` só
    aqui, p/ o módulo carregar sem Ollama instalado/rodando (testes usam fake)."""
    from langchain_ollama import ChatOllama

    kwargs = {"model": modelo}
    if base_url:
        kwargs["base_url"] = base_url
    chat = ChatOllama(**kwargs).with_structured_output(FuzzyExtraction)
    return OllamaProposer(chat, modelo=modelo)
