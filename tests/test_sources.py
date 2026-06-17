import httpx
from sqlalchemy import select

from assetbridge.db import EnrichmentRecord
from assetbridge.graph import build_graph
from assetbridge.identity import AssetIdentity
from assetbridge.sources import HttpEnrichmentSource

# Field-map de exemplo (estilo registro oficial). O contrato real da CVM/B3 é
# plugado aqui quando houver acesso — o conector em si independe dele.
_FIELD_MAP = {"classe_risco": "rating", "setor": "setor", "devedor": "devedor"}


def _ativo() -> AssetIdentity:
    return AssetIdentity(
        tipo="CRI", data_vencimento="2059-05-15", isin="BRIMWLCRI6O9"
    )


def _source(handler) -> HttpEnrichmentSource:
    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://oficial.exemplo"
    )
    return HttpEnrichmentSource(
        client=client, path="/ativos", param="isin", field_map=_FIELD_MAP
    )


def test_conector_oficial_mapeia_resposta_para_enrichment():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["isin"] == "BRIMWLCRI6O9"
        return httpx.Response(
            200,
            json={
                "classe_risco": "AA+",
                "setor": "Logística",
                "ignorado": "x",  # chave fora do field_map → não vira resultado
            },
        )

    results = _source(handler).buscar(_ativo())

    campos = {r.campo: r for r in results}
    assert set(campos) == {"rating", "setor"}
    assert campos["rating"].valor == "AA+"
    assert campos["rating"].fonte == "oficial"
    assert campos["rating"].confianca > 0  # oficial = confiança alta
    # snapshot do que foi buscado (web/registro não é reproduzível — ADR-0010)
    assert campos["rating"].snapshot["classe_risco"] == "AA+"
    assert "BRIMWLCRI6O9" in (campos["rating"].fonte_url or "")


def test_conector_sem_chave_nao_chama_rede():
    chamado = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        chamado["n"] += 1
        return httpx.Response(200, json={})

    ativo = AssetIdentity(tipo="CRI", data_vencimento="2059-05-15")  # sem isin/cnpj
    results = _source(handler).buscar(ativo)

    assert results == []
    assert chamado["n"] == 0


def test_conector_404_degrada_gracioso():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"erro": "nao encontrado"})

    assert _source(handler).buscar(_ativo()) == []


def test_conector_erro_de_rede_degrada_gracioso():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("registro fora do ar")

    assert _source(handler).buscar(_ativo()) == []


def test_conector_no_grafo_grava_caracteristica(session):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"classe_risco": "AA+"})

    src = _source(handler)
    out = build_graph(session, src).invoke({"ativo": _ativo()})

    rec = session.scalars(
        select(EnrichmentRecord).where(EnrichmentRecord.campo == "rating")
    ).first()
    assert rec is not None
    assert rec.fonte == "oficial"
    assert rec.iup == out["iup"]
