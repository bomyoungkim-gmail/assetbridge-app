from datetime import date
from decimal import Decimal

from assetbridge.analytics import posicoes_frame, resumo_por_carteira
from assetbridge.db import PositionRecord


def _pos(session, id_carteira, iup, asof, qtd, pu):
    session.add(
        PositionRecord(
            id_carteira=id_carteira,
            custodiante="BTG",
            iup=iup,
            asof=asof,
            quantidade=Decimal(qtd),
            pu=Decimal(pu),
        )
    )


def test_resumo_por_carteira_agrega_valor_e_contagem(session):
    # Analytics colunar (ADR-0012): Polars carrega a projeção de posição e o
    # DuckDB roda o SQL de agregação por carteira/asof (valor = soma qtd*pu).
    d = date(2026, 6, 1)
    _pos(session, "CART-A", "IUP-1", d, "100", "10")  # 1000
    _pos(session, "CART-A", "IUP-2", d, "5", "200")   # 1000
    _pos(session, "CART-B", "IUP-1", d, "3", "50")    # 150
    session.flush()

    frame = posicoes_frame(session)
    resumo = resumo_por_carteira(frame)

    linhas = {r["id_carteira"]: r for r in resumo.to_dicts()}
    assert linhas["CART-A"]["valor"] == 2000.0
    assert linhas["CART-A"]["n_posicoes"] == 2
    assert linhas["CART-B"]["valor"] == 150.0
    assert linhas["CART-B"]["n_posicoes"] == 1


def test_posicao_pendente_pu_nulo_nao_quebra_agregacao(session):
    # Posição de ativo pendente (HITL) tem iup/pu nulos — coalesce p/ 0, agrega.
    d = date(2026, 6, 1)
    _pos(session, "CART-C", "IUP-9", d, "2", "100")  # 200
    session.add(
        PositionRecord(
            id_carteira="CART-C", custodiante="BTG", iup=None, asof=d,
            quantidade=Decimal("7"), pu=None,
        )
    )
    session.flush()

    resumo = resumo_por_carteira(posicoes_frame(session))
    linha = next(r for r in resumo.to_dicts() if r["id_carteira"] == "CART-C")
    assert linha["valor"] == 200.0       # pu nulo conta como 0
    assert linha["n_posicoes"] == 2      # mas a posição ainda é contada
