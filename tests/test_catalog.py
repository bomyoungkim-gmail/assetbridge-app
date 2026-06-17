from fastapi.testclient import TestClient

from assetbridge.api import app, get_session
from assetbridge.identity import AssetIdentity
from assetbridge.positions import upsert_posicoes
from assetbridge.registry import IupRegistry
from datetime import date
from decimal import Decimal


def _client(session):
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_assets_lista_iups_cunhados(session):
    res = IupRegistry(session).resolve(
        AssetIdentity(tipo="CRI", data_vencimento="2059-05-15", isin="BRIMWLCRI6O9")
    )
    client = _client(session)
    try:
        body = client.get("/assets").json()
        assert body["total"] >= 1
        assert any(a["iup"] == res.iup for a in body["assets"])
    finally:
        app.dependency_overrides.clear()


def test_positions_lista_projecao(session):
    upsert_posicoes(
        session,
        custodiante="BTG",
        id_carteira="CART-1",
        asof=date(2026, 6, 3),
        itens=[
            (
                AssetIdentity(
                    tipo="CRI", data_vencimento="2059-05-15", isin="BRIMWLCRI6O9"
                ),
                Decimal("1000.00"),
                Decimal("500.00"),
            )
        ],
    )
    client = _client(session)
    try:
        body = client.get("/positions").json()
        assert body["total"] >= 1
        pos = body["positions"][0]
        assert pos["id_carteira"] == "CART-1"
        assert pos["custodiante"] == "BTG"
        assert pos["quantidade"] == "1000.00000000"
    finally:
        app.dependency_overrides.clear()


_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<PosicaoAtivosCarteira xmlns:ISO="urn:iso:std:iso:20022:tech:xsd:semt.003.001.04">
  <ISO:Document><ISO:SctiesBalAcctgRpt>
    <ISO:StmtGnlDtls><ISO:StmtDtTm><ISO:Dt>2026-06-03</ISO:Dt></ISO:StmtDtTm></ISO:StmtGnlDtls>
    <ISO:SfkpgAcct><ISO:Id>30306294000145</ISO:Id><ISO:Nm>BTG</ISO:Nm></ISO:SfkpgAcct>
    <ISO:BalForAcct>
      <ISO:FinInstrmId><ISO:ISIN>BR0JJ0CTF000</ISO:ISIN>
        <ISO:OthrId><ISO:Id>55064365000171</ISO:Id><ISO:Tp><ISO:Cd>CNPJ</ISO:Cd></ISO:Tp></ISO:OthrId>
        <ISO:Desc>FUNDO X</ISO:Desc></ISO:FinInstrmId>
      <ISO:AggtBal><ISO:Qty><ISO:Qty><ISO:Qty><ISO:Unit>1</ISO:Unit></ISO:Qty></ISO:Qty></ISO:Qty></ISO:AggtBal>
      <ISO:PricDtls><ISO:Val><ISO:Amt>1</ISO:Amt></ISO:Val></ISO:PricDtls>
      <ISO:AcctBaseCcyAmts><ISO:HldgVal><ISO:Amt>1</ISO:Amt><ISO:Sgn>true</ISO:Sgn></ISO:HldgVal></ISO:AcctBaseCcyAmts>
    </ISO:BalForAcct>
  </ISO:SctiesBalAcctgRpt></ISO:Document>
</PosicaoAtivosCarteira>"""


def test_imports_lista_landing_zone(session):
    client = _client(session)
    try:
        client.post("/ingest", content=_XML, headers={"x-file-name": "p.xml"})
        body = client.get("/imports").json()
        assert body["total"] >= 1
        imp = body["imports"][0]
        assert imp["custodiante"] == "BTG"
        assert len(imp["content_hash"]) == 64
        assert "raw" not in imp  # nunca devolve os bytes brutos
    finally:
        app.dependency_overrides.clear()
