from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import faiss
import numpy as np

# Camada 2 — matching por similaridade (ADR-0012, supera 0002): busca vetorial
# (Faiss) sobre IUPs conhecidos. NÃO-autoritativa: para um ativo sem chave forte,
# sugere os IUPs mais parecidos como AID do HITL — nunca auto-liga identidade
# (fronteira do ADR-0007/0010; o IUP segue determinístico, surrogate, do bruto).


@runtime_checkable
class Embedder(Protocol):
    """Porta de embeddings. O modelo real (ex.: via Ollama) implementa isto
    depois; o matcher só conhece a porta (mesma postura de FieldProposer)."""

    def embed(self, text: str) -> list[float]:
        ...


@dataclass
class MatchCandidate:
    """Candidato a match vetorial — AID do HITL, nunca decisão. `score` é
    similaridade de cosseno em [0,1]; o humano confirma ou descarta."""

    iup: str
    score: float


def _normalizar(v: np.ndarray) -> np.ndarray:
    # Normaliza p/ produto interno = cosseno. Vetor nulo fica nulo (score 0).
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.where(norms == 0, 1.0, norms)


class VectorMatcher:
    """Índice Faiss (produto interno sobre vetores normalizados = cosseno).

    Indexa `(iup, texto)` e, para um texto de consulta, devolve os IUPs mais
    parecidos como candidatos HITL. Pura: não escreve no Postgres nem no
    `iup_registry` — só propõe (fronteira ADR-0007)."""

    def __init__(self, embedder: Embedder, dim: int):
        self._embedder = embedder
        self._index = faiss.IndexFlatIP(dim)
        self._iups: list[str] = []

    def indexar(self, itens: list[tuple[str, str]]) -> None:
        if not itens:
            return
        vetores = np.array(
            [self._embedder.embed(texto) for _, texto in itens], dtype="float32"
        )
        self._index.add(_normalizar(vetores))
        self._iups.extend(iup for iup, _ in itens)

    def candidatos(self, texto: str, k: int = 5) -> list[MatchCandidate]:
        if self._index.ntotal == 0:
            return []
        consulta = _normalizar(
            np.array([self._embedder.embed(texto)], dtype="float32")
        )
        scores, idxs = self._index.search(consulta, min(k, self._index.ntotal))
        return [
            MatchCandidate(iup=self._iups[i], score=float(s))
            for s, i in zip(scores[0], idxs[0])
            if i != -1
        ]
