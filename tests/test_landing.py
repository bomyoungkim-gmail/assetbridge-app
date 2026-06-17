from sqlalchemy import func, select

from assetbridge.db import LandingRecord
from assetbridge.landing import store_raw


def test_store_raw_idempotente_por_hash(session):
    # Landing zone (ADR-0006): bytes idênticos = no-op por hash de conteúdo.
    raw = b"<Document>conteudo bruto</Document>"
    r1 = store_raw(session, "BTG", raw)
    r2 = store_raw(session, "BTG", raw)

    assert r1.id == r2.id
    assert r1.content_hash == r2.content_hash
    count = session.scalar(select(func.count()).select_from(LandingRecord))
    assert count == 1


def test_store_raw_conteudo_diferente_grava_dois(session):
    store_raw(session, "BTG", b"arquivo A")
    store_raw(session, "BTG", b"arquivo B")

    count = session.scalar(select(func.count()).select_from(LandingRecord))
    assert count == 2
