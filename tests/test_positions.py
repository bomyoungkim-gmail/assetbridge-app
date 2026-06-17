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
