from assetbridge.matching import MatchCandidate, VectorMatcher


class _FakeEmbedder:
    """Embedder fake (porta Embedder). O modelo real de embeddings entra depois
    — esta fatia prova o MATCHING vetorial e a fronteira (ADR-0007/0010): propõe
    candidato, nunca auto-liga identidade. Vetores fixos por texto p/ vizinho
    mais próximo determinístico."""

    _MAP = {
        "CRI OPEA logistica": [1.0, 0.0, 0.0],
        "CRA agro soja": [0.0, 1.0, 0.0],
        "DEBENTURE energia": [0.0, 0.0, 1.0],
        # consulta: quase igual ao CRI, leve ruído.
        "CRI parecido sem isin": [0.95, 0.05, 0.0],
    }

    def embed(self, text: str) -> list[float]:
        return self._MAP[text]


def _matcher():
    m = VectorMatcher(_FakeEmbedder(), dim=3)
    m.indexar([
        ("IUP-CRI", "CRI OPEA logistica"),
        ("IUP-CRA", "CRA agro soja"),
        ("IUP-DEB", "DEBENTURE energia"),
    ])
    return m


def test_candidatos_rankeia_vizinho_mais_proximo():
    # Camada 2 (ADR-0012): ativo sem chave forte → busca vetorial sugere os IUPs
    # mais parecidos como AID do HITL. Mais próximo primeiro.
    cands = _matcher().candidatos("CRI parecido sem isin", k=2)

    assert len(cands) == 2
    assert all(isinstance(c, MatchCandidate) for c in cands)
    assert cands[0].iup == "IUP-CRI"  # vizinho mais próximo
    assert cands[0].score >= cands[1].score  # ordenado por similaridade
    assert 0.0 <= cands[0].score <= 1.0


def test_indice_vazio_nao_quebra():
    # Sem nada indexado → sem candidatos (degrada gracioso, não levanta).
    m = VectorMatcher(_FakeEmbedder(), dim=3)
    assert m.candidatos("CRI parecido sem isin", k=3) == []


def test_k_maior_que_indice_retorna_todos():
    # k > tamanho do índice → devolve só o que existe, sem padding/lixo.
    cands = _matcher().candidatos("CRI parecido sem isin", k=10)
    assert len(cands) == 3
    assert {c.iup for c in cands} == {"IUP-CRI", "IUP-CRA", "IUP-DEB"}
