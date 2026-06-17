from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from .db import EnrichmentRecord, PendingResolution
from .identity import AssetIdentity, chave_sintetica

# Campos FORTES (identidade — ADR-0001/0007). A web pode SUGERIR um destes,
# mas nunca aplica: vira candidato HITL. Tudo fora daqui é característica.
IDENTITY_FIELDS = frozenset(
    {"tipo", "data_vencimento", "isin", "cnpj_emissor", "serie_emissao", "is_subordinado"}
)


class EnrichmentResult(BaseModel):
    """Um campo proposto por uma fonte externa (ADR-0010).

    Sempre NÃO-autoritativo: característica vai para a camada `enrichment`;
    campo forte vira candidato HITL. `snapshot` guarda o que foi buscado
    (web não é reproduzível)."""

    campo: str
    valor: str
    fonte: str  # "oficial" (CVM/B3/ANBIMA) | "web" (fallback marcado)
    fonte_url: Optional[str] = None
    confianca: float = 0.0
    query: Optional[str] = None
    snapshot: Optional[dict] = None


@runtime_checkable
class EnrichmentSource(Protocol):
    """Porta de enriquecimento. Conector oficial e web aberta implementam isto;
    o nó `enrich` do grafo só conhece a porta (ADR-0010)."""

    def buscar(self, ativo: AssetIdentity) -> list[EnrichmentResult]:
        ...


def enrich_route(
    session: Session,
    ativo: AssetIdentity,
    iup: Optional[str],
    results: list[EnrichmentResult],
) -> list[str]:
    """Aplica a fronteira do ADR-0010 a cada resultado.

    Característica → grava em `enrichment` (não-autoritativo, atado ao IUP).
    Campo forte → candidato em `pending_resolution` (HITL), NUNCA auto-aplica.
    Retorna os campos de característica gravados."""
    gravados: list[str] = []
    for r in results:
        if r.campo in IDENTITY_FIELDS:
            _enfileirar_candidato(session, ativo, r)
        else:
            session.add(
                EnrichmentRecord(
                    iup=iup,
                    campo=r.campo,
                    valor=r.valor,
                    fonte=r.fonte,
                    fonte_url=r.fonte_url,
                    confianca=r.confianca,
                    query=r.query,
                    snapshot=r.snapshot,
                )
            )
            gravados.append(r.campo)
    session.flush()
    return gravados


def _enfileirar_candidato(
    session: Session, ativo: AssetIdentity, r: EnrichmentResult
) -> None:
    """Campo forte sugerido pela web → candidato HITL. Nunca cunha nem aplica.

    Guarda a sugestão + fonte no payload para o humano avaliar; o IUP segue
    determinístico (ADR-0007). Dedup pela chave provisória + campo sugerido."""
    chave = chave_sintetica(ativo)
    motivo = f"campo forte '{r.campo}' sugerido pela web (fonte {r.fonte})"
    ja = (
        session.query(PendingResolution)
        .filter(
            PendingResolution.chave_provisoria == chave,
            PendingResolution.status == "pending",
            PendingResolution.motivo == motivo,
        )
        .first()
    )
    if ja is not None:
        return
    session.add(
        PendingResolution(
            chave_provisoria=chave,
            payload={
                "ativo": ativo.model_dump(),
                "sugestao": r.model_dump(),
            },
            motivo=motivo,
            status="pending",
        )
    )
    session.flush()
