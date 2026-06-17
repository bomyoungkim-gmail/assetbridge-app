from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select

from assetbridge.api import app
from assetbridge.db import IupRecord, PendingResolution, get_session
from assetbridge.graph import build_graph
from assetbridge.hitl import get_graph
from assetbridge.identity import AssetIdentity


class _NoSource:
    def buscar(self, ativo):
        return []


def test_decision_retoma_grafo_pausado_por_thread_id(session):
    # Mesmo checkpointer p/ pausar (no teste) e retomar (no endpoint).
    cp = MemorySaver()

    def _graph():
        return build_graph(session, _NoSource(), checkpointer=cp)

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_graph] = _graph
    client = TestClient(app)
    try:
        # Item ambíguo entra pelo grafo → pausa no HITL, cria pendência c/ thread_id.
        cfg = {"configurable": {"thread_id": "api-t1"}}
        _graph().invoke(
            {"ativo": AssetIdentity(tipo="CRI", data_vencimento="2059-05-15")}, cfg
        )
        pend = session.scalars(
            select(PendingResolution).where(
                PendingResolution.thread_id == "api-t1"
            )
        ).first()
        assert pend is not None

        # Humano decide via API → endpoint RETOMA o grafo (não chama cunhar_hitl direto).
        r = client.post(
            f"/pending/{pend.id}/decision",
            json={
                "tipo": "CRI",
                "data_vencimento": "2059-05-15",
                "cnpj_emissor": "11222333000181",
                "serie_emissao": "13S",
            },
        )
        assert r.status_code == 200
        iup = r.json()["iup"]
        assert iup.startswith("IUP-")
        # grafo retomou e terminou: pendência resolvida + IUP no registro.
        assert session.get(PendingResolution, pend.id).status == "resolved"
        assert (
            session.scalars(select(IupRecord).where(IupRecord.iup == iup)).first()
            is not None
        )
        # checkpoint não está mais pausado.
        assert _graph().get_state(cfg).next == ()
    finally:
        app.dependency_overrides.clear()


def test_decision_legado_sem_thread_id_ainda_cunha_direto(session):
    # Pendência sem thread_id (criada fora do grafo) → caminho cunhar_hitl direto.
    from assetbridge.registry import IupRegistry

    IupRegistry(session).resolve(
        AssetIdentity(tipo="CRI", data_vencimento="2059-05-15")
    )
    pend = session.scalars(select(PendingResolution)).first()
    assert pend.thread_id is None

    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    try:
        r = client.post(
            f"/pending/{pend.id}/decision",
            json={
                "tipo": "CRI",
                "data_vencimento": "2059-05-15",
                "cnpj_emissor": "11222333000181",
                "serie_emissao": "13S",
            },
        )
        assert r.status_code == 200
        assert r.json()["iup"].startswith("IUP-")
        assert session.get(PendingResolution, pend.id).status == "resolved"
    finally:
        app.dependency_overrides.clear()
