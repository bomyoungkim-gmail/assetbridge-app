from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .db import PositionRecord
from .identity import AssetIdentity
from .registry import IupRegistry

# (identidade, quantidade, pu) — pu opcional
PosicaoItem = tuple[AssetIdentity, Decimal, Decimal | None]
# Resolve uma identidade para o IUP (ou None se pendente HITL).
Resolver = Callable[[AssetIdentity], Optional[str]]


def upsert_posicoes(
    session: Session,
    custodiante: str,
    id_carteira: str,
    asof: date,
    itens: list[PosicaoItem],
    resolver: Optional[Resolver] = None,
) -> int:
    """Grava a projeção de posição (time-series) com delete+replace por
    `(id_carteira, custodiante, asof)` — regra de dia do Oikos no grão de
    carteira (Q6). Outras carteiras e outras datas ficam intactas.

    A posição imutável vive na landing zone; esta projeção é derivada, então
    delete+replace é correto (sem versionamento de linha). Resolve o IUP por
    ativo; ativo pendente (HITL) entra com `iup=None` e é backfillado depois.

    `resolver` é o ponto de resolução do IUP (injetável). Default = resolução
    direta pelo registry (utilitário/harness/testes); o `/ingest` injeta o
    resolver pelo GRAFO (`resolver_via_grafo`) p/ a pendência nascer com
    `thread_id` e a entrada rodar enrich/deliver (ADR-0010)."""
    session.execute(
        delete(PositionRecord).where(
            PositionRecord.id_carteira == id_carteira,
            PositionRecord.custodiante == custodiante,
            PositionRecord.asof == asof,
        )
    )

    if resolver is None:
        reg = IupRegistry(session)
        resolver = lambda identidade: reg.resolve(identidade).iup  # noqa: E731

    n = 0
    for identidade, quantidade, pu in itens:
        session.add(
            PositionRecord(
                id_carteira=id_carteira,
                custodiante=custodiante,
                iup=resolver(identidade),
                asof=asof,
                quantidade=quantidade,
                pu=pu,
            )
        )
        n += 1

    session.flush()
    return n
