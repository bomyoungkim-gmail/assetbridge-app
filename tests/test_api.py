from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select

from assetbridge.api import app, get_session
from assetbridge.db import PendingResolution
from assetbridge.graph import build_graph
from assetbridge.hitl import get_graph


class _NoSource:
    def buscar(self, ativo):
        return []


def _client(session):
    # /resolve-iup roda pelo grafo (ADR-0010): sobrescreve get_graph com um grafo
    # hermético (MemorySaver + fonte vazia), sem checkpointer Postgres nem rede.
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_graph] = lambda: build_graph(
        session, _NoSource(), checkpointer=MemorySaver()
    )
    return TestClient(app)


def test_resolve_iup_estruturado_devolve_iup(session):
    client = _client(session)
    try:
        r = client.post(
            "/resolve-iup",
            json={
                "tipo": "CRI",
                "data_vencimento": "2059-05-15",
                "isin": "BRIMWLCRI6O9",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["novo"] is True
        assert body["pending"] is False
        assert body["iup"].startswith("IUP-")
    finally:
        app.dependency_overrides.clear()


_XML_BTG_POSICAO = b"""<?xml version="1.0" encoding="utf-8"?>
<PosicaoAtivosCarteira xmlns:ISO="urn:iso:std:iso:20022:tech:xsd:semt.003.001.04">
  <ISO:Document>
    <ISO:SctiesBalAcctgRpt>
      <ISO:StmtGnlDtls>
        <ISO:StmtDtTm><ISO:Dt>2026-06-03</ISO:Dt></ISO:StmtDtTm>
      </ISO:StmtGnlDtls>
      <ISO:SfkpgAcct>
        <ISO:Id>30306294000145</ISO:Id>
        <ISO:Nm>BANCO BTG PACTUAL S A</ISO:Nm>
      </ISO:SfkpgAcct>
      <ISO:BalForAcct>
        <ISO:FinInstrmId>
          <ISO:ISIN>BR0JJ0CTF000</ISO:ISIN>
          <ISO:OthrId>
            <ISO:Id>55064365000171</ISO:Id>
            <ISO:Tp><ISO:Cd>CNPJ</ISO:Cd></ISO:Tp>
          </ISO:OthrId>
          <ISO:Desc>OIKOS G FIC FIM CP</ISO:Desc>
        </ISO:FinInstrmId>
        <ISO:AggtBal>
          <ISO:Qty><ISO:Qty><ISO:Qty><ISO:Unit>26162.54377</ISO:Unit></ISO:Qty></ISO:Qty></ISO:Qty>
        </ISO:AggtBal>
        <ISO:PricDtls>
          <ISO:Val><ISO:Amt>1.338588</ISO:Amt></ISO:Val>
        </ISO:PricDtls>
        <ISO:AcctBaseCcyAmts>
          <ISO:HldgVal><ISO:Amt>35125091.80</ISO:Amt><ISO:Sgn>true</ISO:Sgn></ISO:HldgVal>
        </ISO:AcctBaseCcyAmts>
      </ISO:BalForAcct>
      <ISO:AcctBaseCcyTtlAmts>
        <ISO:TtlHldgsValOfStmt>
          <ISO:Amt>35125091.80</ISO:Amt><ISO:Sgn>true</ISO:Sgn>
        </ISO:TtlHldgsValOfStmt>
      </ISO:AcctBaseCcyTtlAmts>
      <ISO:SubAcctDtls>
        <ISO:BalForSubAcct>
          <ISO:FinInstrmId>
            <ISO:ISIN>BRIMWLCRI6O9</ISO:ISIN>
            <ISO:Desc>CRI IPCA</ISO:Desc>
          </ISO:FinInstrmId>
          <ISO:FinInstrmAttrbts>
            <ISO:MtrtyDt>2059-05-15</ISO:MtrtyDt>
            <ISO:DnmtnCcy>BRL</ISO:DnmtnCcy>
          </ISO:FinInstrmAttrbts>
          <ISO:AggtBal>
            <ISO:Qty><ISO:Qty><ISO:Qty><ISO:Unit>1000.00</ISO:Unit></ISO:Qty></ISO:Qty></ISO:Qty>
          </ISO:AggtBal>
          <ISO:PricDtls>
            <ISO:Val><ISO:Amt>500.00</ISO:Amt></ISO:Val>
            <ISO:Tp><ISO:Cd>MRKT</ISO:Cd></ISO:Tp>
          </ISO:PricDtls>
          <ISO:AcctBaseCcyAmts>
            <ISO:HldgVal><ISO:Amt>500000.00</ISO:Amt><ISO:Sgn>true</ISO:Sgn></ISO:HldgVal>
          </ISO:AcctBaseCcyAmts>
        </ISO:BalForSubAcct>
      </ISO:SubAcctDtls>
    </ISO:SctiesBalAcctgRpt>
  </ISO:Document>
</PosicaoAtivosCarteira>"""


def test_ingest_xml_btg_retorna_posicao_completa(session):
    client = _client(session)
    try:
        r = client.post(
            "/ingest",
            content=_XML_BTG_POSICAO,
            headers={"x-file-name": "posicao.xml"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "btg_position_xml"
        assert body["file_name"] == "posicao.xml"
        parsed = body["parsed"]
        assert parsed["fund_cnpj"] == "55064365000171"
        assert parsed["fund_name"] == "OIKOS G FIC FIM CP"
        assert len(parsed["positions"]) == 1
        assert parsed["positions"][0]["quantity"] == "1000.00"
    finally:
        app.dependency_overrides.clear()


def test_ingest_grava_raw_na_landing_zone(session):
    # ADR-0006: /ingest guarda o bruto imutável por hash de conteúdo.
    from sqlalchemy import func, select

    from assetbridge.db import LandingRecord

    client = _client(session)
    try:
        client.post("/ingest", content=_XML_BTG_POSICAO)
        count = session.scalar(select(func.count()).select_from(LandingRecord))
        assert count == 1
    finally:
        app.dependency_overrides.clear()


def test_resolve_iup_roteia_pelo_grafo_pending_tem_thread_id(session):
    # ADR-0010/0008: /resolve-iup deve rodar pelo GRAFO. Item ambíguo PAUSA no
    # interrupt_before(["hitl"]), cria a pendência COM thread_id e devolve o
    # thread_id p/ o consumidor pollar — não pode resolver direto (sem thread_id).
    client = _client(session)
    try:
        r = client.post(
            "/resolve-iup",
            json={"description": "SEM CHAVE FORTE", "cvm_classification": "196"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        assert body["iup"] is None
        thread_id = body["thread_id"]
        assert thread_id  # endpoint gerou e devolveu o thread_id
        # Pendência nasceu pelo forward-run do grafo → carrega o thread_id.
        pend = session.scalars(
            select(PendingResolution).where(
                PendingResolution.thread_id == thread_id
            )
        ).first()
        assert pend is not None
        # O contrato sync/pending fecha: /status responde pelo mesmo thread_id.
        assert client.get(f"/status/{thread_id}").json()["status"] == "pending"
    finally:
        app.dependency_overrides.clear()


def test_resolve_iup_sem_chave_forte_fica_pending(session):
    client = _client(session)
    try:
        r = client.post(
            "/resolve-iup",
            json={"tipo": "CRI", "data_vencimento": "2059-05-15"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["pending"] is True
        assert body["iup"] is None
    finally:
        app.dependency_overrides.clear()


# --- Contrato de integração com o Oikos (ADR-0019/0008) ---
# Oikos manda campos estruturados {isin, cnpj, description, cvm_classification},
# nunca o XML bruto; resposta carrega `status` (resolved|pending) + o IUP.


def test_resolve_iup_contrato_oikos_isin_resolve(session):
    client = _client(session)
    try:
        r = client.post(
            "/resolve-iup",
            json={
                "isin": "BRIMWLCRI6O9",
                "cnpj": None,
                "description": "CRI OPEA LASTRO X",
                "cvm_classification": "196",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "resolved"
        assert body["iup"].startswith("IUP-")
    finally:
        app.dependency_overrides.clear()


def test_resolve_iup_contrato_oikos_cnpj_resolve(session):
    client = _client(session)
    try:
        r = client.post(
            "/resolve-iup",
            json={
                "cnpj": "12345678000199",
                "description": "CDB BANCO X",
                "cvm_classification": "196",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "resolved"
    finally:
        app.dependency_overrides.clear()


def test_resolve_iup_contrato_oikos_sem_chave_forte_pending(session):
    # Sem ISIN nem CNPJ → pending (HITL), nunca drop silencioso.
    client = _client(session)
    try:
        r = client.post(
            "/resolve-iup",
            json={
                "description": "ALGO SEM CHAVE FORTE",
                "cvm_classification": "196",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        assert body["iup"] is None
    finally:
        app.dependency_overrides.clear()
