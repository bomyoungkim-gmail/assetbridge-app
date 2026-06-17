from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .db import PositionRecord
from .identity import AssetIdentity
from .registry import IupRegistry

# (identidade, quantidade, pu) — pu opcional
PosicaoItem = tuple[AssetIdentity, Decimal, Decimal | None]


def upsert_posicoes(
    session: Session,
    custodiante: str,
    id_carteira: str,
    asof: date,
    itens: list[PosicaoItem],
) -> int:
    """Grava a projeção de posição (time-series) com delete+replace por
    `(id_carteira, custodiante, asof)` — regra de dia do Oikos no grão de
    carteira (Q6). Outras carteiras e outras datas ficam intactas.

    A posição imutável vive na landing zone; esta projeção é derivada, então
    delete+replace é correto (sem versionamento de linha). Resolve o IUP por
    ativo; ativo pendente (HITL) entra com `iup=None` e é backfillado depois.
    """
    session.execute(
        delete(PositionRecord).where(
            PositionRecord.id_carteira == id_carteira,
            PositionRecord.custodiante == custodiante,
            PositionRecord.asof == asof,
        )
    )

    reg = IupRegistry(session)
    n = 0
    for identidade, quantidade, pu in itens:
        res = reg.resolve(identidade)
        session.add(
            PositionRecord(
                id_carteira=id_carteira,
                custodiante=custodiante,
                iup=res.iup,
                asof=asof,
                quantidade=quantidade,
                pu=pu,
            )
        )
        n += 1

    session.flush()
    return n
