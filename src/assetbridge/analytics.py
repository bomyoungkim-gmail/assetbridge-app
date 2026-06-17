from __future__ import annotations

import duckdb
import polars as pl
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import PositionRecord

# Analytics colunar em volume (ADR-0012, supera 0002): a projeção de posição
# (Postgres, system of record) é carregada num frame Polars e o DuckDB roda o
# SQL analítico por cima. Postgres segue autoritativo; isto é camada DERIVADA de
# leitura — não escreve nada. É o que o harness de carga (fatia 3) exercita.


def posicoes_frame(session: Session) -> pl.DataFrame:
    """Carrega a projeção `positions` num DataFrame Polars (colunar).

    Decimal/None viram float/null no frame analítico — a verdade monetária
    exata segue no Postgres; aqui é agregação/analytics, não contabilidade."""
    rows = session.scalars(select(PositionRecord)).all()
    return pl.DataFrame(
        {
            "id_carteira": [r.id_carteira for r in rows],
            "custodiante": [r.custodiante for r in rows],
            "iup": [r.iup for r in rows],
            "asof": [r.asof for r in rows],
            "quantidade": [float(r.quantidade) if r.quantidade is not None else None for r in rows],
            "pu": [float(r.pu) if r.pu is not None else None for r in rows],
        }
    )


def resumo_por_carteira(frame: pl.DataFrame) -> pl.DataFrame:
    """Agrega valor (Σ qtd·pu) e nº de posições por carteira/data, via DuckDB.

    DuckDB lê o frame Polars direto (replacement scan — daí `frame` ser usado
    apesar de o linter não ver). `pu` nulo (posição pendente HITL) entra como 0
    no valor, mas a posição ainda é CONTADA — nada some silenciosamente (mesma
    postura do ADR-0005)."""
    return (
        duckdb.connect()
        .execute(
            """
            SELECT
                id_carteira,
                "asof",
                COUNT(*) AS n_posicoes,
                SUM(quantidade * COALESCE(pu, 0)) AS valor
            FROM frame
            GROUP BY id_carteira, "asof"
            ORDER BY id_carteira, "asof"
            """
        )
        .pl()
    )
