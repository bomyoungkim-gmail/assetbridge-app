from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

from pydantic import BaseModel

from .identity import AssetIdentity

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from .db import ExtractionRecord

# Campos FORTES (ADR-0007): saem de regex determinístico; o LLM NUNCA os
# preenche. Tudo fora daqui é fuzzy e vem do proposer (classe, série, subord.).
STRONG_FIELDS = frozenset({"isin", "cnpj_emissor", "data_vencimento"})

# Formatos PADRONIZADOS (não específicos de custodiante — por isso são seguros
# antes de amostra real, ADR-0002): ISIN ISO 6166, CNPJ, data ISO 8601.
_ISIN_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}\d)\b")
_CNPJ_RE = re.compile(r"\b(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})\b")
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


class FieldProposal(BaseModel):
    """Campo proposto pelo LLM (fuzzy). Carrega `modelo` para auditoria e
    reprocessamento em massa quando o modelo melhora (extração versionada,
    ADR-0007). Confiança alimenta a calibração futura da zona cinzenta."""

    campo: str
    valor: str
    confianca: float = 0.0
    modelo: Optional[str] = None


@runtime_checkable
class FieldProposer(Protocol):
    """Porta do extrator fuzzy (LLM). O Ollama real e os prompts por custodiante
    implementam isto depois (bloqueado por amostra, ADR-0002); o nó `extract` do
    grafo só conhece a porta."""

    def propor(self, raw: str) -> list[FieldProposal]:
        ...


def _isin(raw: str) -> Optional[str]:
    m = _ISIN_RE.search(raw)
    return m.group(1) if m else None


def _cnpj(raw: str) -> Optional[str]:
    m = _CNPJ_RE.search(raw)
    if m is None:
        return None
    return re.sub(r"\D", "", m.group(1))  # normaliza: só dígitos


def _vencimento(raw: str) -> Optional[str]:
    # Assume uma data por enquanto; desambiguar venc×emissão exige layout do
    # custodiante → deferido à fatia de extrator por custodiante (ADR-0002).
    m = _DATE_RE.search(raw)
    return m.group(1) if m else None


def montar_identidade(raw: str, proposals: list[FieldProposal]) -> AssetIdentity:
    """Monta a identidade a partir de proposals JÁ obtidas (sem chamar o LLM).

    Separado de `extrair_identidade` p/ o grafo obter as proposals uma vez (caro)
    e reusá-las na proveniência (`registrar_extracao`), sem invocar o LLM 2x."""
    fuzzy = {p.campo: p.valor for p in proposals if p.campo not in STRONG_FIELDS}
    return AssetIdentity(
        tipo=fuzzy.get("tipo", "DESCONHECIDO"),
        data_vencimento=_vencimento(raw) or "",
        isin=_isin(raw),
        cnpj_emissor=_cnpj(raw),
        serie_emissao=fuzzy.get("serie_emissao"),
        is_subordinado=str(fuzzy.get("is_subordinado", "")).upper() == "SUB",
    )


def extrair_identidade(raw: str, proposer: FieldProposer) -> AssetIdentity:
    """Camada 1 (híbrida): regex manda nos campos fortes; o LLM só propõe fuzzy.

    Fronteira do ADR-0007: o proposer NUNCA toca isin/cnpj/data — mesmo que
    proponha, é ignorado. Sem campo forte por regex → identidade nasce sem
    chave forte e a resolução a manda para HITL (não inventa)."""
    return montar_identidade(raw, proposer.propor(raw))


def registrar_extracao(
    session: "Session",
    raw: str,
    iup: Optional[str],
    proposals: list[FieldProposal],
) -> list["ExtractionRecord"]:
    """Persiste a proveniência da extração fuzzy (extração VERSIONADA, ADR-0007).

    Grava `modelo`+`confianca` por campo FUZZY, atado ao bruto por `raw_hash`
    (re-extração reencontra pelo bruto, ADR-0006). Campo forte do LLM é ignorado
    (vem de regex). Versiona pelo MODELO: re-extração com o mesmo `(raw_hash,
    campo, modelo)` SOBRESCREVE (mais recente vence — cobre não-determinismo do
    LLM e backfill do `iup` pós-HITL); modelo novo gera linha nova. Upsert →
    idempotente por versão, sem duplicatas. Devolve as linhas atuais do bruto."""
    from sqlalchemy import func, select
    from sqlalchemy.dialects.postgresql import insert

    from .db import ExtractionRecord

    raw_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    # Dedup por (campo, modelo) na entrada: o ON CONFLICT não pode afetar a mesma
    # linha 2x na mesma sentença; último vence (consistente com o upsert).
    por_chave = {
        (p.campo, p.modelo): p
        for p in proposals
        if p.campo not in STRONG_FIELDS
    }
    if not por_chave:
        return []

    valores = [
        {
            "raw_hash": raw_hash,
            "iup": iup,
            "campo": p.campo,
            "valor": p.valor,
            "confianca": p.confianca,
            "modelo": p.modelo,
        }
        for p in por_chave.values()
    ]
    stmt = insert(ExtractionRecord).values(valores)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_extraction_versao",
        set_={
            "valor": stmt.excluded.valor,
            "confianca": stmt.excluded.confianca,
            "iup": stmt.excluded.iup,
            "created_at": func.now(),  # marca a recência da última extração
        },
    )
    session.execute(stmt)
    session.flush()
    return list(
        session.scalars(
            select(ExtractionRecord).where(ExtractionRecord.raw_hash == raw_hash)
        )
    )
