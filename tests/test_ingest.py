from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import func, select

from assetbridge.api import app, get_session
from assetbridge.db import (
    ExcludedRecord,
    LandingRecord,
    PendingResolution,
    PositionRecord,
)
from assetbridge.graph import build_graph
from assetbridge.hitl import get_graph


class _NoSource:
    def buscar(self, ativo):
        return []


def _client(session):
    # /ingest roda pelo grafo (ADR-0010): grafo hermético (MemorySaver + fonte
    # vazia) via override do get_graph, sem checkpointer Postgres nem rede.
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_graph] = lambda: build_graph(
        session, _NoSource(), checkpointer=MemorySaver()
    )
    return TestClient(app)


# Sub-posição com ISIN (chave forte) → resolve IUP determinístico (ADR-0003).
_XML_FORTE = b"""<?xml version="1.0" encoding="utf-8"?>
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
    <ISO:SubAcctDtls><ISO:BalForSubAcct>
      <ISO:FinInstrmId><ISO:ISIN>BRIMWLCRI6O9</ISO:ISIN><ISO:Desc>CRI IPCA</ISO:Desc></ISO:FinInstrmId>
      <ISO:FinInstrmAttrbts><ISO:MtrtyDt>2059-05-15</ISO:MtrtyDt><ISO:DnmtnCcy>BRL</ISO:DnmtnCcy></ISO:FinInstrmAttrbts>
      <ISO:AggtBal><ISO:Qty><ISO:Qty><ISO:Qty><ISO:Unit>1000.00</ISO:Unit></ISO:Qty></ISO:Qty></ISO:Qty></ISO:AggtBal>
      <ISO:PricDtls><ISO:Val><ISO:Amt>500.00</ISO:Amt></ISO:Val><ISO:Tp><ISO:Cd>MRKT</ISO:Cd></ISO:Tp></ISO:PricDtls>
      <ISO:AcctBaseCcyAmts><ISO:HldgVal><ISO:Amt>500000.00</ISO:Amt><ISO:Sgn>true</ISO:Sgn></ISO:HldgVal></ISO:AcctBaseCcyAmts>
    </ISO:BalForSubAcct></ISO:SubAcctDtls>
  </ISO:SctiesBalAcctgRpt></ISO:Document>
</PosicaoAtivosCarteira>"""


# Sub-posição sem ISIN nem CNPJ → sem chave forte → HITL (ADR-0005/0007).
_XML_FRACO = b"""<?xml version="1.0" encoding="utf-8"?>
<PosicaoAtivosCarteira xmlns:ISO="urn:iso:std:iso:20022:tech:xsd:semt.003.001.04">
  <ISO:Document><ISO:SctiesBalAcctgRpt>
    <ISO:StmtGnlDtls><ISO:StmtDtTm><ISO:Dt>2026-06-04</ISO:Dt></ISO:StmtDtTm></ISO:StmtGnlDtls>
    <ISO:SfkpgAcct><ISO:Id>30306294000145</ISO:Id><ISO:Nm>BTG</ISO:Nm></ISO:SfkpgAcct>
    <ISO:BalForAcct>
      <ISO:FinInstrmId><ISO:ISIN>BR0JJ0CTF000</ISO:ISIN>
        <ISO:OthrId><ISO:Id>55064365000171</ISO:Id><ISO:Tp><ISO:Cd>CNPJ</ISO:Cd></ISO:Tp></ISO:OthrId>
        <ISO:Desc>FUNDO X</ISO:Desc></ISO:FinInstrmId>
      <ISO:AggtBal><ISO:Qty><ISO:Qty><ISO:Qty><ISO:Unit>1</ISO:Unit></ISO:Qty></ISO:Qty></ISO:Qty></ISO:AggtBal>
      <ISO:PricDtls><ISO:Val><ISO:Amt>1</ISO:Amt></ISO:Val></ISO:PricDtls>
      <ISO:AcctBaseCcyAmts><ISO:HldgVal><ISO:Amt>1</ISO:Amt><ISO:Sgn>true</ISO:Sgn></ISO:HldgVal></ISO:AcctBaseCcyAmts>
    </ISO:BalForAcct>
    <ISO:SubAcctDtls><ISO:BalForSubAcct>
      <ISO:FinInstrmId><ISO:Desc>DEBENTURE SEM ISIN</ISO:Desc></ISO:FinInstrmId>
      <ISO:FinInstrmAttrbts><ISO:MtrtyDt>2030-01-01</ISO:MtrtyDt><ISO:DnmtnCcy>BRL</ISO:DnmtnCcy></ISO:FinInstrmAttrbts>
      <ISO:AggtBal><ISO:Qty><ISO:Qty><ISO:Qty><ISO:Unit>10.00</ISO:Unit></ISO:Qty></ISO:Qty></ISO:Qty></ISO:AggtBal>
      <ISO:PricDtls><ISO:Val><ISO:Amt>100.00</ISO:Amt></ISO:Val><ISO:Tp><ISO:Cd>MRKT</ISO:Cd></ISO:Tp></ISO:PricDtls>
      <ISO:AcctBaseCcyAmts><ISO:HldgVal><ISO:Amt>1000.00</ISO:Amt><ISO:Sgn>true</ISO:Sgn></ISO:HldgVal></ISO:AcctBaseCcyAmts>
    </ISO:BalForSubAcct></ISO:SubAcctDtls>
  </ISO:SctiesBalAcctgRpt></ISO:Document>
</PosicaoAtivosCarteira>"""


# Fundo com MARGEM (breakdown de saldo) — vira posição sintética; NÃO é ativo
# identificável → exclusão auditada (ADR-0005), nunca HITL.
_XML_MARGEM = b"""<?xml version="1.0" encoding="utf-8"?>
<PosicaoAtivosCarteira xmlns:ISO="urn:iso:std:iso:20022:tech:xsd:semt.003.001.04">
  <ISO:Document><ISO:SctiesBalAcctgRpt>
    <ISO:StmtGnlDtls><ISO:StmtDtTm><ISO:Dt>2026-06-05</ISO:Dt></ISO:StmtDtTm></ISO:StmtGnlDtls>
    <ISO:SfkpgAcct><ISO:Id>30306294000145</ISO:Id><ISO:Nm>BTG</ISO:Nm></ISO:SfkpgAcct>
    <ISO:BalForAcct>
      <ISO:FinInstrmId><ISO:ISIN>BR0JJ0CTF000</ISO:ISIN>
        <ISO:OthrId><ISO:Id>55064365000171</ISO:Id><ISO:Tp><ISO:Cd>CNPJ</ISO:Cd></ISO:Tp></ISO:OthrId>
        <ISO:Desc>FUNDO X</ISO:Desc></ISO:FinInstrmId>
      <ISO:AggtBal><ISO:Qty><ISO:Qty><ISO:Qty><ISO:Unit>1</ISO:Unit></ISO:Qty></ISO:Qty></ISO:Qty></ISO:AggtBal>
      <ISO:PricDtls><ISO:Val><ISO:Amt>1</ISO:Amt></ISO:Val></ISO:PricDtls>
      <ISO:AcctBaseCcyAmts><ISO:HldgVal><ISO:Amt>1</ISO:Amt><ISO:Sgn>true</ISO:Sgn></ISO:HldgVal></ISO:AcctBaseCcyAmts>
      <ISO:BalBrkdwn>
        <ISO:SubBalTp><ISO:Prtry><ISO:Id>MRGN</ISO:Id><ISO:SchmeNm>GARANTIA</ISO:SchmeNm></ISO:Prtry></ISO:SubBalTp>
        <ISO:AddtlBalBrkdwnDtls>
          <ISO:SubBalTp><ISO:Prtry><ISO:Id>MRGN</ISO:Id><ISO:SchmeNm>MARGEM</ISO:SchmeNm></ISO:Prtry></ISO:SubBalTp>
          <ISO:Qty><ISO:Qty><ISO:FaceAmt>2500.00</ISO:FaceAmt></ISO:Qty></ISO:Qty>
        </ISO:AddtlBalBrkdwnDtls>
      </ISO:BalBrkdwn>
    </ISO:BalForAcct>
  </ISO:SctiesBalAcctgRpt></ISO:Document>
</PosicaoAtivosCarteira>"""


def test_ingest_cunha_iup_e_grava_posicao(session):
    # Chave forte (ISIN) → /ingest cunha IUP e persiste a posição (direção a).
    client = _client(session)
    try:
        r = client.post("/ingest", content=_XML_FORTE, headers={"x-file-name": "p.xml"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ingested"
        assert body["id_carteira"] == "55064365000171"
        assert body["asof"] == "2026-06-03"
        assert body["posicoes"] == 1
        assert body["pendencias"] == 0

        assets = client.get("/assets").json()
        assert assets["total"] == 1
        positions = client.get("/positions").json()
        assert positions["total"] == 1
        pos = positions["positions"][0]
        assert pos["id_carteira"] == "55064365000171"
        assert pos["custodiante"] == "BTG"
        assert pos["iup"] is not None
        assert pos["quantidade"] == "1000.00000000"
    finally:
        app.dependency_overrides.clear()


def test_ingest_sem_chave_forte_vira_pendencia(session):
    # Sem ISIN/CNPJ → posição com IUP nulo + pendência HITL (nunca cunha sozinho).
    client = _client(session)
    try:
        body = client.post("/ingest", content=_XML_FRACO).json()
        assert body["posicoes"] == 1
        assert body["pendencias"] == 1

        pending = client.get("/pending").json()["pending"]
        assert len(pending) == 1

        assert client.get("/assets").json()["total"] == 0  # nada cunhado
        pos = client.get("/positions").json()["positions"][0]
        assert pos["iup"] is None
    finally:
        app.dependency_overrides.clear()


def test_ingest_sem_chave_forte_cria_pendencia_com_thread_id(session):
    # ADR-0010/0008: /ingest roda pelo GRAFO. Posição sem chave forte pausa no
    # interrupt_before(["hitl"]) e a pendência nasce COM thread_id — habilita o
    # poll/resume em produção (antes a pendência do /ingest ficava sem thread_id).
    client = _client(session)
    try:
        body = client.post("/ingest", content=_XML_FRACO).json()
        assert body["pendencias"] == 1

        pend = session.scalars(select(PendingResolution)).first()
        assert pend is not None
        assert pend.thread_id is not None
        # O contrato sync/pending fecha pelo mesmo thread_id.
        assert client.get(f"/status/{pend.thread_id}").json()["status"] == "pending"
    finally:
        app.dependency_overrides.clear()


def test_ingest_duplicado_e_noop(session):
    # Reingestão de bytes idênticos = no-op (ADR-0008): não regrava nem recunha.
    client = _client(session)
    try:
        client.post("/ingest", content=_XML_FORTE)
        segundo = client.post("/ingest", content=_XML_FORTE).json()
        assert segundo["status"] == "duplicate"

        landing = session.scalar(select(func.count()).select_from(LandingRecord))
        assert landing == 1
        positions = session.scalar(select(func.count()).select_from(PositionRecord))
        assert positions == 1
    finally:
        app.dependency_overrides.clear()


def test_ingest_margem_sintetica_vai_para_exclusao_auditada(session):
    # MARGEM não é ativo identificável → exclusão auditada, fora do HITL (ADR-0005).
    client = _client(session)
    try:
        body = client.post("/ingest", content=_XML_MARGEM).json()
        assert body["excluidos"] == 1

        excl = session.scalar(select(func.count()).select_from(ExcludedRecord))
        assert excl == 1
        assert client.get("/pending").json()["pending"] == []
    finally:
        app.dependency_overrides.clear()
