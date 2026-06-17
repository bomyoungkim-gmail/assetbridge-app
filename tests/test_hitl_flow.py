from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select

from assetbridge.db import IupRecord, PendingResolution
from assetbridge.graph import build_graph
from assetbridge.identity import AssetIdentity


class _NoSource:
    def buscar(self, ativo):
        return []


def _ambiguo() -> AssetIdentity:
    # Sem ISIN nem CNPJ → resolução não pode auto-cunhar (ADR-0007) → HITL.
    return AssetIdentity(tipo="CRI", data_vencimento="2059-05-15")


def _forte() -> AssetIdentity:
    return AssetIdentity(
        tipo="CRI", data_vencimento="2030-01-01", isin="BRIMWLCRI6O9"
    )


def test_grafo_pausa_no_hitl_e_persiste_thread_id(session):
    g = build_graph(session, _NoSource(), checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t-1"}}

    out = g.invoke({"ativo": _ambiguo()}, cfg)

    # interrupt_before("hitl"): parou antes de gravar o IUP definitivo.
    assert out.get("iup") is None
    assert g.get_state(cfg).next == ("hitl",)
    # thread_id do checkpoint vira coluna da pendência (CONTEXT/Q1).
    row = session.scalars(select(PendingResolution)).first()
    assert row.thread_id == "t-1"


def test_grafo_resume_com_decisao_humana_cunha_iup(session):
    g = build_graph(session, _NoSource(), checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t-2"}}
    g.invoke({"ativo": _ambiguo()}, cfg)  # pausa no HITL

    # Humano resolve a ambiguidade fornecendo chave forte; grafo retoma.
    decidido = AssetIdentity(
        tipo="CRI",
        data_vencimento="2059-05-15",
        cnpj_emissor="11222333000181",
        serie_emissao="13S",
    )
    g.update_state(cfg, {"decisao": decidido})
    out = g.invoke(None, cfg)

    assert out["iup"].startswith("IUP-")
    rec = session.scalars(
        select(IupRecord).where(IupRecord.iup == out["iup"])
    ).first()
    assert rec is not None


def test_grafo_com_checkpointer_chave_forte_nao_pausa(session):
    # Certeza forte (ISIN) → auto-cunha inline, sem interrupt (ADR-0007).
    g = build_graph(session, _NoSource(), checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t-3"}}

    out = g.invoke({"ativo": _forte()}, cfg)

    assert out["iup"].startswith("IUP-")
    assert g.get_state(cfg).next == ()  # terminou, não pausou
