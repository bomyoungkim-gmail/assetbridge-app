import io
import os
import time
import zipfile

from assetbridge.cvm_ops import CvmCriCache
from assetbridge.identity import AssetIdentity

_CSV = (
    "Codigo_ISIN;Data_Referencia;Versao;Classificacao_Risco_Atual;Situacao\n"
    "BRIMWLCRI6O9;2026-02-01;1;AA;Adimplente\n"
)


def _zip_bytes(year: int, csv_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"inf_mensal_cri_classe_{year}.csv", csv_text.encode("latin-1"))
    return buf.getvalue()


def _ativo() -> AssetIdentity:
    return AssetIdentity(tipo="CRI", data_vencimento="", isin="BRIMWLCRI6O9")


def test_baixa_extrai_cacheia_e_constroi_source(tmp_path):
    chamadas = {"n": 0}

    def fetch():
        chamadas["n"] += 1
        return _zip_bytes(2026, _CSV)

    src = CvmCriCache(tmp_path, year=2026, fetch_zip=fetch).load_source()

    out = {r.campo: r for r in src.buscar(_ativo())}
    assert out["rating"].valor == "AA"
    assert (tmp_path / "inf_mensal_cri_classe_2026.csv").exists()  # cacheou
    assert chamadas["n"] == 1


def test_cache_fresco_nao_rebaixa(tmp_path):
    CvmCriCache(
        tmp_path, 2026, fetch_zip=lambda: _zip_bytes(2026, _CSV)
    ).load_source()

    def boom():
        raise AssertionError("não deveria rebaixar com cache fresco")

    # Nova instância, fetch que explode → deve servir do cache em disco.
    src = CvmCriCache(tmp_path, 2026, fetch_zip=boom).load_source()
    assert src.buscar(_ativo())


def test_force_rebaixa_mesmo_fresco(tmp_path):
    chamadas = {"n": 0}

    def fetch():
        chamadas["n"] += 1
        return _zip_bytes(2026, _CSV)

    cache = CvmCriCache(tmp_path, 2026, fetch_zip=fetch)
    cache.load_source()
    cache.load_source(force=True)
    assert chamadas["n"] == 2


def test_cache_stale_rebaixa_por_ttl(tmp_path):
    chamadas = {"n": 0}

    def fetch():
        chamadas["n"] += 1
        return _zip_bytes(2026, _CSV)

    cache = CvmCriCache(tmp_path, 2026, ttl_days=7, fetch_zip=fetch)
    cache.load_source()
    # envelhece o arquivo além do TTL → próximo load rebaixa.
    p = tmp_path / "inf_mensal_cri_classe_2026.csv"
    old = time.time() - 8 * 86400
    os.utime(p, (old, old))
    cache.load_source()
    assert chamadas["n"] == 2
