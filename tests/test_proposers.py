from assetbridge.extraction import STRONG_FIELDS, extrair_identidade
from assetbridge.proposers import FuzzyExtraction, OllamaProposer


class _FakeStructured:
    """Imita um ChatModel.with_structured_output(...): .invoke(prompt) → schema."""

    def __init__(self, out: FuzzyExtraction):
        self._out = out

    def invoke(self, prompt):
        return self._out


def test_ollama_proposer_mapeia_fuzzy_para_fieldproposal():
    fake = _FakeStructured(
        FuzzyExtraction(tipo="CRI", serie_emissao="13S", subordinacao="SUB")
    )
    props = {p.campo: p for p in OllamaProposer(fake, modelo="qwen3:8b").propor("x")}

    assert props["tipo"].valor == "CRI"
    assert props["tipo"].modelo == "qwen3:8b"  # extração versionada (ADR-0007)
    assert props["serie_emissao"].valor == "13S"
    assert props["is_subordinado"].valor == "SUB"


def test_ollama_proposer_nunca_emite_campo_forte_e_omite_vazios():
    # Schema do LLM nem inclui campo forte; ainda assim filtramos por segurança.
    fake = _FakeStructured(FuzzyExtraction(tipo="CRI"))
    props = OllamaProposer(fake).propor("x")
    campos = {p.campo for p in props}

    assert campos == {"tipo"}
    assert STRONG_FIELDS.isdisjoint(campos)


def test_ollama_proposer_alimenta_extrair_identidade():
    # Fronteira ADR-0007: regex manda nos campos fortes; LLM só no fuzzy.
    fake = _FakeStructured(FuzzyExtraction(tipo="CDB"))
    raw = "CDB BANCO X, CNPJ 11.222.333/0001-81, venc 2030-01-01"
    ativo = extrair_identidade(raw, OllamaProposer(fake))

    assert ativo.tipo == "CDB"  # do LLM
    assert ativo.cnpj_emissor == "11222333000181"  # do regex
    assert ativo.data_vencimento == "2030-01-01"
