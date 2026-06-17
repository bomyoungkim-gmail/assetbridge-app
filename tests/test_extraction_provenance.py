from assetbridge.db import ExtractionRecord
from assetbridge.extraction import FieldProposal, registrar_extracao


def _rows(session, raw_hash=None):
    q = session.query(ExtractionRecord)
    if raw_hash is not None:
        q = q.filter(ExtractionRecord.raw_hash == raw_hash)
    return q.order_by(ExtractionRecord.id).all()


def test_registra_proveniencia_fuzzy_com_modelo_e_confianca(session):
    # ADR-0007: a extração fuzzy é VERSIONADA — guarda modelo + confiança por
    # campo p/ reprocessar em massa quando o modelo melhora. Campo forte (vem de
    # regex, não do LLM) NUNCA entra na proveniência do proposer.
    raw = "CRI OPEA, série 13S, subordinado"
    proposals = [
        FieldProposal(campo="tipo", valor="CRI", confianca=0.9, modelo="qwen3:8b"),
        FieldProposal(campo="serie_emissao", valor="13S", confianca=0.7, modelo="qwen3:8b"),
        # campo forte proposto pelo LLM → ignorado (ADR-0007).
        FieldProposal(campo="cnpj_emissor", valor="99999999999999", confianca=0.3, modelo="qwen3:8b"),
    ]

    registros = registrar_extracao(session, raw, iup="IUP-abc", proposals=proposals)

    assert {r.campo for r in registros} == {"tipo", "serie_emissao"}
    salvos = _rows(session)
    assert {(r.campo, r.valor, r.modelo, r.confianca) for r in salvos} == {
        ("tipo", "CRI", "qwen3:8b", 0.9),
        ("serie_emissao", "13S", "qwen3:8b", 0.7),
    }
    assert all(r.iup == "IUP-abc" for r in salvos)
    # mesmo raw → mesmo hash (re-extração reencontra pelo bruto, ADR-0006).
    assert len({r.raw_hash for r in salvos}) == 1


def test_reextracao_mesmo_modelo_sobrescreve_mantem_recente(session):
    # MESMO bruto + MESMO modelo rodado de novo → 1 linha (não duplica), com o
    # valor/confiança/iup MAIS RECENTES. Cobre não-determinismo do LLM e o
    # backfill do iup quando a resolução sai do HITL depois.
    raw = "CRI sem isin, classe incerta"
    v1 = [FieldProposal(campo="tipo", valor="DEBENTURE", confianca=0.4, modelo="qwen3:8b")]
    v2 = [FieldProposal(campo="tipo", valor="CRI", confianca=0.85, modelo="qwen3:8b")]

    registrar_extracao(session, raw, iup=None, proposals=v1)      # 1ª passada, sem IUP
    registrar_extracao(session, raw, iup="IUP-novo", proposals=v2)  # re-extração

    salvos = _rows(session)
    assert len(salvos) == 1                 # sobrescreveu, não duplicou
    assert salvos[0].valor == "CRI"         # mais recente vence
    assert salvos[0].confianca == 0.85
    assert salvos[0].iup == "IUP-novo"      # backfill do iup


def test_reextracao_com_modelo_novo_versiona_nao_sobrescreve(session):
    # Modelo melhora → roda de novo sobre o MESMO bruto. Mantém histórico
    # (nova versão coexiste), não apaga a anterior — é o que torna reprocessável.
    raw = "CRA do agro, série unica"
    v1 = [FieldProposal(campo="tipo", valor="CRA", confianca=0.5, modelo="llama3.1:8b")]
    v2 = [FieldProposal(campo="tipo", valor="CRA", confianca=0.95, modelo="qwen3:8b")]

    registrar_extracao(session, raw, iup="IUP-xyz", proposals=v1)
    registrar_extracao(session, raw, iup="IUP-xyz", proposals=v2)

    salvos = _rows(session)
    assert len(salvos) == 2
    assert {r.modelo for r in salvos} == {"llama3.1:8b", "qwen3:8b"}
    assert len({r.raw_hash for r in salvos}) == 1  # mesmo bruto, duas versões
