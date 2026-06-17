from sqlalchemy import select

from assetbridge.db import EnrichmentRecord
from assetbridge.graph import build_graph
from assetbridge.identity import AssetIdentity
from assetbridge.sources import CvmCriSource, load_cvm_cri_classe_index

# CSV no formato real do informe mensal de CRI da CVM (tabela `classe`, ';').
_CSV = (
    "Codigo_ISIN;Data_Referencia;Versao;Classificacao_Risco_Atual;Situacao\n"
    "BRIMWLCRI6O9;2026-01-01;1;A;Adimplente\n"
    "BRIMWLCRI6O9;2026-02-01;1;AA;Adimplente\n"  # mais recente vence
    ";2026-02-01;1;X;Y\n"  # ISIN vazio → ignorado
)


def _ativo() -> AssetIdentity:
    return AssetIdentity(tipo="CRI", data_vencimento="", isin="BRIMWLCRI6O9")


def test_loader_indexa_por_isin_mantendo_data_referencia_mais_recente():
    idx = load_cvm_cri_classe_index(_CSV)

    assert set(idx) == {"BRIMWLCRI6O9"}  # ISIN vazio ignorado
    assert idx["BRIMWLCRI6O9"]["Classificacao_Risco_Atual"] == "AA"


def test_cvm_source_mapeia_colunas_reais_para_enrichment():
    idx = {
        "BRIMWLCRI6O9": {
            "Codigo_ISIN": "BRIMWLCRI6O9",
            "Classificacao_Risco_Atual": "AA",
            "Situacao": "Adimplente",
            "Nivel_Subordinacao": "",  # vazio → omitido
            "Taxas_Indexadores": "IPCA + 6%",
            "Classe": "Sênior",
        }
    }
    out = {r.campo: r for r in CvmCriSource(idx).buscar(_ativo())}

    assert out["rating"].valor == "AA"
    assert out["rating"].fonte == "oficial"
    assert out["situacao"].valor == "Adimplente"
    assert out["indexador"].valor == "IPCA + 6%"
    assert out["classe_cvm"].valor == "Sênior"
    assert "subordinacao" not in out  # campo vazio não vira resultado
    assert out["rating"].snapshot["Codigo_ISIN"] == "BRIMWLCRI6O9"


def test_cvm_source_isin_ausente_ou_sem_isin_retorna_vazio():
    src = CvmCriSource({"OUTRO": {"Classificacao_Risco_Atual": "AA"}})
    assert src.buscar(_ativo()) == []  # ISIN não está no índice
    assert src.buscar(AssetIdentity(tipo="CRI", data_vencimento="", cnpj_emissor="X")) == []


def test_cvm_source_no_grafo_grava_rating(session):
    idx = {"BRIMWLCRI6O9": {"Classificacao_Risco_Atual": "AA"}}
    out = build_graph(session, CvmCriSource(idx)).invoke({"ativo": _ativo()})

    rec = session.scalars(
        select(EnrichmentRecord).where(EnrichmentRecord.campo == "rating")
    ).first()
    assert rec is not None
    assert rec.valor == "AA"
    assert rec.fonte == "oficial"
    assert rec.iup == out["iup"]
