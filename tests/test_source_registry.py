from fastapi.testclient import TestClient

from assetbridge.api import app, get_session
from assetbridge.db import SourceConfig
from assetbridge.source_registry import ChainEnrichmentSource, build_db_sources
from assetbridge.identity import AssetIdentity
from assetbridge.enrichment import EnrichmentResult
from assetbridge.sources import HttpEnrichmentSource


def _client(session):
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_cadastra_e_lista_fonte(session):
    client = _client(session)
    try:
        r = client.post(
            "/sources",
            json={
                "nome": "B3 instrumentos",
                "tipo": "api",
                "base_url": "https://api.b3.example",
                "path": "/instrumento",
                "param": "isin",
                "field_map": {"setor": "setor", "nome_longo": "nome_longo"},
                "confianca": 0.9,
            },
        )
        assert r.status_code == 201
        criada = r.json()
        assert criada["id"] > 0
        assert criada["nome"] == "B3 instrumentos"
        assert criada["enabled"] is True

        listadas = client.get("/sources").json()["sources"]
        assert any(s["nome"] == "B3 instrumentos" for s in listadas)
    finally:
        app.dependency_overrides.clear()


def test_nome_duplicado_conflita(session):
    client = _client(session)
    try:
        body = {"nome": "dup", "tipo": "api", "base_url": "http://x", "path": "/y"}
        assert client.post("/sources", json=body).status_code == 201
        assert client.post("/sources", json=body).status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_remove_fonte(session):
    client = _client(session)
    try:
        cid = client.post(
            "/sources", json={"nome": "tmp", "tipo": "api", "base_url": "http://x"}
        ).json()["id"]
        assert client.delete(f"/sources/{cid}").status_code == 204
        assert all(s["id"] != cid for s in client.get("/sources").json()["sources"])
    finally:
        app.dependency_overrides.clear()


def test_toggle_enabled(session):
    client = _client(session)
    try:
        cid = client.post(
            "/sources", json={"nome": "t", "tipo": "api", "base_url": "http://x"}
        ).json()["id"]
        r = client.patch(f"/sources/{cid}", json={"enabled": False})
        assert r.status_code == 200
        assert r.json()["enabled"] is False
    finally:
        app.dependency_overrides.clear()


def test_build_db_sources_so_api_habilitada_liga_viva(session):
    # api habilitada → HttpEnrichmentSource viva; scraping/csv catalogados mas
    # execução deferida (ADR-0010); api desabilitada → fora da composição.
    session.add(
        SourceConfig(
            nome="api-on",
            tipo="api",
            base_url="https://x",
            path="/i",
            field_map={"setor": "setor"},
        )
    )
    session.add(SourceConfig(nome="scrap", tipo="scraping", base_url="https://y"))
    session.add(
        SourceConfig(nome="api-off", tipo="api", base_url="https://z", enabled=False)
    )
    session.flush()

    fontes = build_db_sources(session)
    assert len(fontes) == 1
    assert isinstance(fontes[0], HttpEnrichmentSource)


class _Fake:
    def __init__(self, results, boom=False):
        self._results = results
        self._boom = boom

    def buscar(self, ativo):
        if self._boom:
            raise RuntimeError("fonte caiu")
        return self._results


def test_chain_concatena_e_degrada_gracioso():
    r1 = EnrichmentResult(campo="rating", valor="AA", fonte="oficial", confianca=0.9)
    r2 = EnrichmentResult(campo="setor", valor="agro", fonte="oficial", confianca=0.9)
    chain = ChainEnrichmentSource([_Fake([r1]), _Fake([], boom=True), _Fake([r2])])

    out = chain.buscar(AssetIdentity(tipo="CRI", data_vencimento="", isin="X"))

    campos = {r.campo for r in out}
    assert campos == {"rating", "setor"}  # fonte que caiu não derruba as outras
