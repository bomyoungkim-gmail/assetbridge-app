from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from assetbridge.db import PositionRecord
from assetbridge.identity import AssetIdentity
from assetbridge.positions import upsert_posicoes


def _pos(isin, qty, pu="100.0"):
    return (
        AssetIdentity(tipo="CRI", data_vencimento="2059-05-15", isin=isin),
        Decimal(qty),
        Decimal(pu),
    )


def test_upsert_grava_posicao_com_iup_resolvido(session):
    n = upsert_posicoes(
        session, "BTG", "CART1", date(2030, 1, 1), [_pos("BRAAAACRI0A0", "1000")]
    )
    assert n == 1
    row = session.scalars(select(PositionRecord)).first()
    assert row.iup.startswith("IUP-")
    assert row.id_carteira == "CART1"
    assert row.custodiante == "BTG"
    assert row.quantidade == Decimal("1000")


def test_sub_posicoes_mesmo_iup_agregam_em_uma_linha(session):
    # BTG reporta o MESMO instrumento em vários sub-accounts (disponível/garantia).
    # Grão = uma linha por (carteira, custodiante, IUP, asof): agrega somando a
    # quantidade (conserva valor; ADR-0005, "nada some"). PU igual → PU mantido.
    d = date(2030, 1, 1)
    n = upsert_posicoes(
        session,
        "BTG",
        "CART1",
        d,
        [_pos("BRAAAACRI0A0", "1000", "100.0"), _pos("BRAAAACRI0A0", "500", "100.0")],
    )
    assert n == 1
    rows = session.scalars(select(PositionRecord)).all()
    assert len(rows) == 1
    assert rows[0].quantidade == Decimal("1500")
    assert rows[0].pu == Decimal("100.0")


def test_agregacao_de_pu_divergente_conserva_valor(session):
    # PU divergente entre sub-posições do mesmo IUP → média PONDERADA pela
    # quantidade, para o valor total (Σ qtd·pu) bater (conservação, ADR-0005).
    d = date(2030, 1, 1)
    upsert_posicoes(
        session,
        "BTG",
        "CART1",
        d,
        [_pos("BRAAAACRI0A0", "100", "10.0"), _pos("BRAAAACRI0A0", "300", "20.0")],
    )
    row = session.scalars(select(PositionRecord)).one()
    assert row.quantidade == Decimal("400")
    # (100*10 + 300*20) / 400 = 7000/400 = 17.5
    assert row.pu == Decimal("17.5")


def test_delete_replace_por_carteira_e_asof(session):
    # Q6: re-ingestão do mesmo (carteira, asof) substitui o dia inteiro.
    d = date(2030, 1, 1)
    upsert_posicoes(
        session, "BTG", "CART1", d, [_pos("BRAAAACRI0A0", "1000"), _pos("BRBBBBCRI0B0", "5")]
    )
    upsert_posicoes(session, "BTG", "CART1", d, [_pos("BRAAAACRI0A0", "2000")])

    rows = session.scalars(
        select(PositionRecord).where(PositionRecord.id_carteira == "CART1")
    ).all()
    assert len(rows) == 1
    assert rows[0].quantidade == Decimal("2000")


def test_asof_diferente_acumula_serie_temporal(session):
    upsert_posicoes(session, "BTG", "CART1", date(2030, 1, 1), [_pos("BRAAAACRI0A0", "1000")])
    upsert_posicoes(session, "BTG", "CART1", date(2030, 1, 2), [_pos("BRAAAACRI0A0", "1100")])

    count = session.scalar(select(func.count()).select_from(PositionRecord))
    assert count == 2


def test_replace_de_uma_carteira_nao_afeta_outra(session):
    d = date(2030, 1, 1)
    upsert_posicoes(session, "BTG", "CART1", d, [_pos("BRAAAACRI0A0", "1000")])
    upsert_posicoes(session, "BTG", "CART2", d, [_pos("BRAAAACRI0A0", "9")])
    upsert_posicoes(session, "BTG", "CART1", d, [_pos("BRAAAACRI0A0", "2000")])

    cart2 = session.scalars(
        select(PositionRecord).where(PositionRecord.id_carteira == "CART2")
    ).all()
    assert len(cart2) == 1
    assert cart2[0].quantidade == Decimal("9")
