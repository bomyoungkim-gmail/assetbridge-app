from assetbridge.enrichment import EnrichmentResult
from assetbridge.identity import AssetIdentity
from assetbridge.sources import HybridEnrichmentSource


class _Fake:
    def __init__(self, results=None, erro=None):
        self._results = results or []
        self._erro = erro

    def buscar(self, ativo):
        if self._erro is not None:
            raise self._erro
        return self._results


def _ativo() -> AssetIdentity:
    return AssetIdentity(tipo="CRI", data_vencimento="2059-05-15", isin="BRIMWLCRI6O9")


def _res(campo, valor, fonte, conf):
    return EnrichmentResult(campo=campo, valor=valor, fonte=fonte, confianca=conf)


def test_oficial_manda_web_so_preenche_lacunas_com_confianca_rebaixada():
    oficial = _Fake([_res("rating", "AA+", "oficial", 0.95)])
    web = _Fake(
        [
            _res("rating", "AAA", "web", 0.9),  # campo já coberto pelo oficial → ignorado
            _res("setor", "Logística", "web", 0.9),  # lacuna → entra, rebaixado
        ]
    )
    out = {r.campo: r for r in HybridEnrichmentSource(oficial, web, cap_web=0.7).buscar(_ativo())}

    assert out["rating"].fonte == "oficial"
    assert out["rating"].valor == "AA+"  # oficial vence
    assert out["setor"].fonte == "web"
    assert out["setor"].confianca == 0.7  # rebaixada ao teto


def test_oficial_vazio_web_preenche_tudo():
    oficial = _Fake([])
    web = _Fake([_res("rating", "AAA", "web", 0.9)])
    out = HybridEnrichmentSource(oficial, web, cap_web=0.7).buscar(_ativo())

    assert len(out) == 1
    assert out[0].fonte == "web"
    assert out[0].confianca == 0.7


def test_web_falha_retorna_so_oficial():
    oficial = _Fake([_res("rating", "AA+", "oficial", 0.95)])
    web = _Fake(erro=TimeoutError("web fora"))
    out = HybridEnrichmentSource(oficial, web).buscar(_ativo())

    assert [r.campo for r in out] == ["rating"]
    assert out[0].fonte == "oficial"
