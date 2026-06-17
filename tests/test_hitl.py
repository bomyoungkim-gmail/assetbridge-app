from fastapi.testclient import TestClient
from sqlalchemy import select

from assetbridge.api import app, get_session
from assetbridge.db import HitlDecision, IupRecord, PendingResolution
from assetbridge.identity import AssetIdentity
from assetbridge.registry import IupRegistry


def _client(session):
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def _abre_pendencia(session):
    # sem chave forte → registry enfileira pendência
    IupRegistry(session).resolve(
        AssetIdentity(tipo="CRI", data_vencimento="2059-05-15")
    )
    return session.scalars(select(PendingResolution)).first()


def test_get_pending_lista_pendencias_abertas(session):
    _abre_pendencia(session)
    client = _client(session)
    try:
        r = client.get("/pending")
        assert r.status_code == 200
        body = r.json()
        assert len(body["pending"]) == 1
        assert body["pending"][0]["motivo"]
    finally:
        app.dependency_overrides.clear()


def test_decision_com_chave_forte_cunha_iup_e_resolve(session):
    pend = _abre_pendencia(session)
    client = _client(session)
    try:
        # humano fornece CNPJ + série → vira chave forte
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


def test_decision_sem_chave_forte_cunha_surrogate_chave_null(session):
    # ADR-0004: IUP de HITL sem chave forte fica com chave_sintetica NULL.
    pend = _abre_pendencia(session)
    client = _client(session)
    try:
        r = client.post(
            f"/pending/{pend.id}/decision",
            json={"tipo": "CRI", "data_vencimento": "2059-05-15"},
        )
        assert r.status_code == 200
        iup = r.json()["iup"]
        rec = session.scalars(
            select(IupRecord).where(IupRecord.iup == iup)
        ).first()
        assert rec.chave_sintetica is None
    finally:
        app.dependency_overrides.clear()


def test_decision_e_pegajosa_idempotente(session):
    # Decisão humana persistida: redecidir devolve a mesma, não re-cunha (ADR-0007).
    pend = _abre_pendencia(session)
    client = _client(session)
    try:
        body = {"tipo": "CRI", "data_vencimento": "2059-05-15"}
        r1 = client.post(f"/pending/{pend.id}/decision", json=body)
        r2 = client.post(f"/pending/{pend.id}/decision", json=body)
        assert r1.json()["iup"] == r2.json()["iup"]
        decisoes = session.scalars(
            select(HitlDecision).where(HitlDecision.pending_id == pend.id)
        ).all()
        assert len(decisoes) == 1
    finally:
        app.dependency_overrides.clear()


def test_decision_pendencia_inexistente_404(session):
    client = _client(session)
    try:
        r = client.post(
            "/pending/999999/decision",
            json={"tipo": "CRI", "data_vencimento": "2059-05-15"},
        )
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()
