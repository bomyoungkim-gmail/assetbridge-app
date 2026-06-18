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

    # BTG reporta o mesmo instrumento em vários sub-accounts (disponível/garantia).
    # Grão = uma linha por (carteira, custodiante, IUP, asof): agrega as
    # sub-posições do mesmo IUP somando a quantidade e ponderando o PU pela
    # quantidade (conserva o valor total Σ qtd·pu — ADR-0005, "nada some").
    # IUP nulo (pendente HITL) NÃO agrega: cada pendência fica sua linha (NULLs
    # são distintos no unique do Postgres) e é backfillada individualmente.
    agregadas: dict[str, dict] = {}
    pendentes: list[tuple[Decimal, Decimal | None]] = []
    for identidade, quantidade, pu in itens:
        iup = resolver(identidade)
        if iup is None:
            pendentes.append((quantidade, pu))
            continue
        acc = agregadas.setdefault(iup, {"qtd": Decimal("0"), "valor": Decimal("0"), "pu_nulo": False})
        acc["qtd"] += quantidade
        if pu is None:
            acc["pu_nulo"] = True
        else:
            acc["valor"] += quantidade * pu

    n = 0
    for iup, acc in agregadas.items():
        # PU agregado = média ponderada (valor/qtd). Se algum PU veio nulo ou a
        # qtd total é zero, não dá para ponderar → PU nulo (preenchido depois).
        pu_agg = (
            acc["valor"] / acc["qtd"]
            if not acc["pu_nulo"] and acc["qtd"] != 0
            else None
        )
        session.add(
            PositionRecord(
                id_carteira=id_carteira,
                custodiante=custodiante,
                iup=iup,
                asof=asof,
                quantidade=acc["qtd"],
                pu=pu_agg,
            )
        )
        n += 1

    for quantidade, pu in pendentes:
        session.add(
            PositionRecord(
                id_carteira=id_carteira,
                custodiante=custodiante,
                iup=None,
                asof=asof,
                quantidade=quantidade,
                pu=pu,
            )
        )
        n += 1

    session.flush()
    return n
