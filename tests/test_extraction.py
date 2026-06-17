from assetbridge.extraction import FieldProposal, extrair_identidade
from assetbridge.identity import AssetIdentity


class _FakeProposer:
    """Proposer LLM fake (porta FieldProposer).

    O LLM real (Ollama) e os prompts por custodiante entram por fatia, bloqueados
    por amostra real (ADR-0002). Esta fatia prova a FRONTEIRA do ADR-0007:
    campos fortes mandam; o LLM só propõe fuzzy e NUNCA inventa CNPJ/data."""

    def __init__(self, propostas):
        self._propostas = propostas

    def propor(self, raw: str) -> list[FieldProposal]:
        return self._propostas


def test_campos_fortes_vem_de_regex_deterministico():
    # CNPJ, ISIN e data saem de regex (formato padronizado), não do LLM.
    raw = "CRI OPEA lastro X, ISIN BRIMWLCRI6O9, CNPJ 11.222.333/0001-81, venc 2059-05-15"
    proposer = _FakeProposer(
        [
            FieldProposal(campo="tipo", valor="CRI", confianca=0.9, modelo="fake-v1"),
            FieldProposal(campo="serie_emissao", valor="13S", confianca=0.8, modelo="fake-v1"),
        ]
    )
    ativo = extrair_identidade(raw, proposer)

    assert isinstance(ativo, AssetIdentity)
    assert ativo.isin == "BRIMWLCRI6O9"
    assert ativo.cnpj_emissor == "11222333000181"  # normalizado, só dígitos
    assert ativo.data_vencimento == "2059-05-15"
    # fuzzy vem do proposer
    assert ativo.tipo == "CRI"
    assert ativo.serie_emissao == "13S"


def test_llm_nunca_inventa_campo_forte():
    # ADR-0007: o LLM propõe um CNPJ, mas o texto não tem CNPJ por regex →
    # identidade fica SEM CNPJ (vai a HITL na resolução), nunca usa o do LLM.
    raw = "CRI sem chave forte de emissor, venc 2059-05-15"
    proposer = _FakeProposer(
        [
            FieldProposal(campo="tipo", valor="CRI", confianca=0.9, modelo="fake-v1"),
            # LLM tenta cravar um CNPJ — deve ser IGNORADO (campo forte).
            FieldProposal(campo="cnpj_emissor", valor="99999999999999", confianca=0.4, modelo="fake-v1"),
        ]
    )
    ativo = extrair_identidade(raw, proposer)

    assert ativo.cnpj_emissor is None
    assert ativo.tipo == "CRI"


def test_regex_forte_vence_proposta_conflitante_do_llm():
    # Texto TEM CNPJ; o LLM propõe outro CNPJ → manda o do regex.
    raw = "CDB BANCO X, CNPJ 11.222.333/0001-81, venc 2030-01-01"
    proposer = _FakeProposer(
        [
            FieldProposal(campo="tipo", valor="CDB", confianca=0.9, modelo="fake-v1"),
            FieldProposal(campo="cnpj_emissor", valor="00000000000000", confianca=0.5, modelo="fake-v1"),
        ]
    )
    ativo = extrair_identidade(raw, proposer)

    assert ativo.cnpj_emissor == "11222333000181"  # regex manda, não o LLM
