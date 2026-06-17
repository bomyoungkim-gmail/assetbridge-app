from sqlalchemy import select

from assetbridge.db import EnrichmentRecord, IupRecord, PendingResolution
from assetbridge.enrichment import EnrichmentResult
from assetbridge.extraction import FieldProposal
from assetbridge.graph import build_graph
from assetbridge.identity import AssetIdentity


class _FakeSource:
    """Fonte de enriquecimento fake (porta EnrichmentSource).

    Conector oficial (CVM/B3) e web aberta implementam a mesma interface
    depois — esta fatia prova a FRONTEIRA, não os conectores (ADR-0010)."""

    def __init__(self, results=None, erro=None):
        self._results = results or []
        self._erro = erro

    def buscar(self, ativo: AssetIdentity) -> list[EnrichmentResult]:
        if self._erro is not None:
            raise self._erro
        return self._results


def _ativo_btg() -> AssetIdentity:
    # BTG entrega dado pobre: ISIN forte presente, sem características.
    return AssetIdentity(
        tipo="CRI", data_vencimento="2030-01-01", isin="BRIMWLCRI6O9"
    )


def test_caracteristica_web_grava_enrichment_nao_autoritativo(session):
    # Característica (não-identidade) → camada enrichment, ligada ao IUP cunhado.
    src = _FakeSource(
        [
            EnrichmentResult(
                campo="rating",
                valor="AA+",
                fonte="oficial",
                fonte_url="https://www.cvm.gov.br/ativo/x",
                confianca=0.95,
            )
        ]
    )
    out = build_graph(session, src).invoke({"ativo": _ativo_btg()})

    rec = session.scalars(
        select(EnrichmentRecord).where(EnrichmentRecord.campo == "rating")
    ).first()
    assert rec is not None
    assert rec.valor == "AA+"
    assert rec.fonte == "oficial"
    # Não-autoritativo mas atado ao IUP que a resolução cunhou.
    assert rec.iup == out["iup"]
    # Identidade NUNCA tocada pela web: registro autoritativo segue limpo.
    assert out["iup"].startswith("IUP-")


def test_campo_forte_da_web_vira_candidato_hitl_nunca_auto(session):
    # Web sugere CNPJ faltante (campo forte) → candidato HITL, jamais auto.
    src = _FakeSource(
        [
            EnrichmentResult(
                campo="cnpj_emissor",
                valor="11222333000181",
                fonte="web",
                fonte_url="https://site.exemplo/x",
                confianca=0.6,
            )
        ]
    )
    build_graph(session, src).invoke({"ativo": _ativo_btg()})

    cands = session.scalars(select(PendingResolution)).all()
    assert len(cands) == 1
    assert "web" in (cands[0].motivo or "").lower()
    # Campo forte da web NÃO vira característica autoritativa.
    assert session.scalars(select(EnrichmentRecord)).first() is None


def test_falha_da_fonte_entrega_sem_enriquecimento_best_effort(session):
    # Enriquecimento é turbinador: falha/timeout → entrega segue, nunca bloqueia.
    src = _FakeSource(erro=TimeoutError("fonte web indisponível"))
    out = build_graph(session, src).invoke({"ativo": _ativo_btg()})

    assert out["iup"].startswith("IUP-")
    assert session.scalars(select(EnrichmentRecord)).first() is None
    assert session.scalars(select(PendingResolution)).first() is None


class _FakeProposer:
    def __init__(self, propostas):
        self._propostas = propostas

    def propor(self, raw):
        return self._propostas


def test_grafo_extrai_texto_bruto_e_resolve_iup(session):
    # Path não-BTG: chega `raw` (texto), nó extract roda Camada 1 → identidade
    # com chave forte (ISIN/CNPJ via regex) → resolução cunha IUP.
    src = _FakeSource([])
    proposer = _FakeProposer(
        [FieldProposal(campo="tipo", valor="CRI", confianca=0.9, modelo="fake-v1")]
    )
    raw = "CRI lastro X, ISIN BRIMWLCRI6O9, venc 2059-05-15"
    out = build_graph(session, src, proposer=proposer).invoke({"raw": raw})

    assert out["iup"].startswith("IUP-")
    rec = session.scalars(
        select(IupRecord).where(IupRecord.iup == out["iup"])
    ).first()
    assert rec is not None


def test_grafo_persiste_proveniencia_versionada_da_extracao(session):
    # ADR-0007: ao extrair texto bruto, o grafo grava a proveniência fuzzy
    # (modelo+confiança) atada ao IUP cunhado — base do reprocessamento em massa.
    from assetbridge.db import ExtractionRecord

    src = _FakeSource([])
    proposer = _FakeProposer(
        [
            FieldProposal(campo="tipo", valor="CRI", confianca=0.9, modelo="qwen3:8b"),
            FieldProposal(campo="serie_emissao", valor="13S", confianca=0.7, modelo="qwen3:8b"),
        ]
    )
    raw = "CRI lastro X, ISIN BRIMWLCRI6O9, venc 2059-05-15, serie 13S"
    out = build_graph(session, src, proposer=proposer).invoke({"raw": raw})

    provs = session.scalars(select(ExtractionRecord)).all()
    assert {p.campo for p in provs} == {"tipo", "serie_emissao"}
    assert all(p.modelo == "qwen3:8b" for p in provs)
    assert all(p.iup == out["iup"] for p in provs)  # atada ao IUP cunhado
