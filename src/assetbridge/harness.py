from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .ingest import ingest_btg
from .parser_btg import parse_position_xml

# Harness de carga sobre carteiras BTG (ADR-0012, supera as 300 sintéticas da
# spec): replica um template BTG real em N carteiras DISTINTAS (CNPJ de fundo
# variado) e roda o pipeline ponta-a-ponta medindo throughput. Mede o pipeline
# contra o dado que o sistema realmente processa — não carga fictícia.

_CNPJ_BASE = 10_000_000_000_000  # fora do range do custodiante do template


@dataclass
class LoadReport:
    """Métricas de uma rodada de carga + invariantes de corretude.

    `duplicados` = carteiras cuja reingestão foi no-op (ADR-0008); permite
    provar idempotência sob carga. `carteiras_por_seg` é o throughput observado."""

    carteiras: int
    posicoes: int
    pendencias: int
    excluidos: int
    duplicados: int
    segundos: float

    @property
    def carteiras_por_seg(self) -> float:
        return self.carteiras / self.segundos if self.segundos else 0.0


def gerar_carteiras_btg(template: bytes, n: int) -> list[bytes]:
    """Gera N carteiras BTG distintas a partir de um template real.

    Cada variante troca o CNPJ do fundo (= `id_carteira`, ADR-0005) por um
    distinto → bytes distintos → hash distinto (sem dedup na landing zone). O
    CNPJ do custodiante e o resto do XML ficam intactos."""
    cnpj_fundo = parse_position_xml(template).fund_cnpj.encode("ascii")
    if not cnpj_fundo:
        raise ValueError("template BTG sem CNPJ de fundo para variar")
    return [
        template.replace(cnpj_fundo, f"{_CNPJ_BASE + i:014d}".encode("ascii"))
        for i in range(n)
    ]


def rodar_carga(session: Session, raws: list[bytes]) -> LoadReport:
    """Roda o pipeline (`ingest_btg`) sobre cada carteira, medindo o tempo.

    Acumula os contadores do ciclo (posições/pendências/exclusões) e conta as
    reingestões no-op (`duplicate`) — invariantes verificáveis sob carga."""
    posicoes = pendencias = excluidos = duplicados = 0
    inicio = time.perf_counter()
    for raw in raws:
        res = ingest_btg(session, raw)
        if res.status == "duplicate":
            duplicados += 1
            continue
        posicoes += res.posicoes
        pendencias += res.pendencias
        excluidos += res.excluidos
    segundos = time.perf_counter() - inicio

    return LoadReport(
        carteiras=len(raws),
        posicoes=posicoes,
        pendencias=pendencias,
        excluidos=excluidos,
        duplicados=duplicados,
        segundos=segundos,
    )
