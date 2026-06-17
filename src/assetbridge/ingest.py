from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .cvm import classificar
from .db import ExcludedRecord, LandingRecord, PositionRecord
from .identity import AssetIdentity
from .landing import store_raw
from .parser_btg import ParsedFundPosition, parse_position_xml
from .positions import upsert_posicoes

_CUSTODIANTE = "BTG"


@dataclass
class IngestResult:
    """Resultado da ingestão direção a (standalone) de um XML BTG.

    `status='duplicate'` = reingestão de bytes idênticos (no-op, ADR-0008);
    senão `ingested` com os contadores do ciclo (resolução + projeção)."""

    status: str  # ingested | duplicate
    id_carteira: str
    asof: str
    posicoes: int
    pendencias: int
    excluidos: int
    parsed: ParsedFundPosition


def ingest_btg(session: Session, raw: bytes) -> IngestResult:
    """Ciclo completo da direção a (ADR-0005/0006/0008) sobre o XML BTG.

    1. Landing zone por hash — reingestão idêntica é no-op (não recunha IUP nem
       reescreve posição).
    2. Roteia as posições em três vias (ADR-0005): chave forte → resolve/cunha
       IUP; sem chave forte → posição com IUP nulo + pendência HITL; posição
       sintética (MARGEM/`BBDN`, injetada pelo parser) → exclusão AUDITADA, fora
       do HITL (não é ativo identificável).
    3. Projeção de posição por `(id_carteira, custodiante, asof)` com
       delete+replace (Q6) via `upsert_posicoes`.
    """
    parsed = parse_position_xml(raw)
    id_carteira = parsed.fund_cnpj or parsed.fund_isin or "?"
    asof = parsed.reference_date

    content_hash = hashlib.sha256(raw).hexdigest()
    ja_existe = session.scalars(
        select(LandingRecord).where(LandingRecord.content_hash == content_hash)
    ).first()
    if ja_existe is not None:
        return IngestResult(
            status="duplicate",
            id_carteira=id_carteira,
            asof=asof.isoformat(),
            posicoes=0,
            pendencias=0,
            excluidos=0,
            parsed=parsed,
        )

    store_raw(session, _CUSTODIANTE, raw)

    itens = []
    excluidos = 0
    for pos in parsed.positions:
        # Posição sintética do parser (MARGEM): ajuste de saldo, não ativo →
        # exclusão auditada, nunca HITL nem cunho (ADR-0005).
        if pos.price_type == "BBDN":
            inst = pos.instrument
            session.add(
                ExcludedRecord(
                    custodiante=_CUSTODIANTE,
                    motivo="posição sintética (breakdown de saldo), não-instrumento",
                    payload={"description": inst.description, "amount": str(pos.price)},
                )
            )
            excluidos += 1
            continue

        inst = pos.instrument
        itens.append(
            (
                AssetIdentity(
                    # Classe pelo código CVM estruturado + refino por Desc (ADR-0005).
                    tipo=classificar(inst.cvm_classification or "", inst.description or ""),
                    data_vencimento="",
                    isin=inst.isin,
                    cnpj_emissor=inst.cnpj,
                ),
                pos.quantity,
                pos.price,
            )
        )

    posicoes = upsert_posicoes(
        session,
        custodiante=_CUSTODIANTE,
        id_carteira=id_carteira,
        asof=asof,
        itens=itens,
    )

    pendencias = session.scalar(
        select(func.count())
        .select_from(PositionRecord)
        .where(
            PositionRecord.id_carteira == id_carteira,
            PositionRecord.custodiante == _CUSTODIANTE,
            PositionRecord.asof == asof,
            PositionRecord.iup.is_(None),
        )
    )

    return IngestResult(
        status="ingested",
        id_carteira=id_carteira,
        asof=asof.isoformat(),
        posicoes=posicoes,
        pendencias=pendencias or 0,
        excluidos=excluidos,
        parsed=parsed,
    )
