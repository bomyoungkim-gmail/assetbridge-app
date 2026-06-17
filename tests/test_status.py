from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select

from assetbridge.api import app
from assetbridge.db import PendingResolution, get_session
from assetbridge.graph import build_graph
from assetbridge.hitl import get_graph
from assetbridge.identity import AssetIdentity


class _NoSource:
    def buscar(self, ativo):
        return []


def test_status_poll_pending_depois_resolved(session):
    cp = MemorySaver()

    def _graph():
        return build_graph(session, _NoSource(), checkpointer=cp)

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_graph] = _graph
    client = TestClient(app)
    try:
        cfg = {"configurable": {"thread_id": "poll-t1"}}
        _graph().invoke(
            {"ativo": AssetIdentity(tipo="CRI", data_vencimento="2059-05-15")}, cfg
        )

        # Consumidor faz poll antes da decisão → pending, IUP nulo (nunca trava).
        r = client.get("/status/poll-t1")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"
        assert r.json()["iup"] is None

        # Humano decide.
        pend = session.scalars(
            select(PendingResolution).where(
                PendingResolution.thread_id == "poll-t1"
            )
        ).first()
        client.post(
            f"/pending/{pend.id}/decision",
            json={
                "tipo": "CRI",
                "data_vencimento": "2059-05-15",
                "cnpj_emissor": "11222333000181",
                "serie_emissao": "13S",
            },
        )

        # Poll depois → resolved + IUP p/ o consumidor backfillar.
        r2 = client.get("/status/poll-t1")
        assert r2.status_code == 200
        assert r2.json()["status"] == "resolved"
        assert r2.json()["iup"].startswith("IUP-")
    finally:
        app.dependency_overrides.clear()


def test_status_thread_desconhecido_404(session):
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    try:
        assert client.get("/status/nao-existe").status_code == 404
    finally:
        app.dependency_overrides.clear()
