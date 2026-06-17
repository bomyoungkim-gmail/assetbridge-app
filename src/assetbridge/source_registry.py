from __future__ import annotations

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SourceConfig, get_session
from .enrichment import EnrichmentResult, EnrichmentSource
from .identity import AssetIdentity
from .sources import HttpEnrichmentSource

router = APIRouter()

# Tipos catalogáveis. Só `api` liga vivo no grafo nesta fatia; `csv`/`scraping`
# ficam registrados mas com execução DEFERIDA (bloqueada por amostra, ADR-0010).
TIPOS = frozenset({"api", "csv", "scraping"})
TIPOS_VIVOS = frozenset({"api"})


class ChainEnrichmentSource:
    """Compõe N fontes numa só porta `EnrichmentSource` (ADR-0010/0011).

    Concatena os resultados de cada fonte; best-effort por fonte — uma que
    levanta exceção (rede/404/payload) não derruba as demais. Mantém a postura
    de turbinador: a entrega nunca bloqueia por enriquecimento."""

    def __init__(self, fontes: list[EnrichmentSource]):
        self._fontes = fontes

    def buscar(self, ativo: AssetIdentity) -> list[EnrichmentResult]:
        out: list[EnrichmentResult] = []
        for fonte in self._fontes:
            try:
                out.extend(fonte.buscar(ativo))
            except Exception:
                continue  # degrada gracioso — fonte caída não trava as outras
        return out


def build_db_sources(session: Session) -> list[EnrichmentSource]:
    """Monta as fontes VIVAS cadastradas no registry (ADR-0011).

    Só linhas `enabled` de `tipo='api'` viram `HttpEnrichmentSource` (uma por
    linha, contrato plugado pelo `field_map`). `csv`/`scraping` são cadastráveis
    e visíveis no GET /sources, mas a execução fica deferida (sem amostra)."""
    rows = session.scalars(
        select(SourceConfig).where(
            SourceConfig.enabled.is_(True), SourceConfig.tipo.in_(TIPOS_VIVOS)
        )
    ).all()
    fontes: list[EnrichmentSource] = []
    for r in rows:
        if not r.base_url:
            continue
        fontes.append(
            HttpEnrichmentSource(
                client=httpx.Client(base_url=r.base_url),
                path=r.path or "",
                field_map=r.field_map or {},
                param=r.param,
                fonte="oficial",
                confianca=r.confianca,
            )
        )
    return fontes


class SourceIn(BaseModel):
    nome: str
    tipo: str
    base_url: Optional[str] = None
    path: Optional[str] = None
    param: str = "isin"
    field_map: Optional[dict[str, str]] = None
    confianca: float = 0.9
    enabled: bool = True


class SourcePatch(BaseModel):
    enabled: bool


def _dump(s: SourceConfig) -> dict:
    return {
        "id": s.id,
        "nome": s.nome,
        "tipo": s.tipo,
        "base_url": s.base_url,
        "path": s.path,
        "param": s.param,
        "field_map": s.field_map,
        "confianca": s.confianca,
        "enabled": s.enabled,
        # `vivo` = liga no grafo agora; csv/scraping ficam catalogados/deferidos.
        "vivo": s.enabled and s.tipo in TIPOS_VIVOS,
    }


@router.get("/sources")
def listar_sources(session: Session = Depends(get_session)):
    """Catálogo de fontes de enriquecimento cadastradas (ADR-0011)."""
    rows = session.scalars(select(SourceConfig).order_by(SourceConfig.id)).all()
    return {"sources": [_dump(s) for s in rows]}


@router.post("/sources", status_code=201)
def criar_source(body: SourceIn, session: Session = Depends(get_session)):
    """Cadastra fonte nova (operador, sem mexer em env/código — ADR-0011)."""
    if body.tipo not in TIPOS:
        raise HTTPException(status_code=422, detail=f"tipo inválido: {body.tipo}")
    ja = session.scalars(
        select(SourceConfig).where(SourceConfig.nome == body.nome)
    ).first()
    if ja is not None:
        raise HTTPException(status_code=409, detail="nome de fonte já existe")
    s = SourceConfig(**body.model_dump())
    session.add(s)
    session.flush()
    return _dump(s)


@router.patch("/sources/{source_id}")
def alterar_source(
    source_id: int, body: SourcePatch, session: Session = Depends(get_session)
):
    """Liga/desliga uma fonte (gate de execução no grafo)."""
    s = session.get(SourceConfig, source_id)
    if s is None:
        raise HTTPException(status_code=404, detail="fonte não encontrada")
    s.enabled = body.enabled
    session.flush()
    return _dump(s)


@router.delete("/sources/{source_id}", status_code=204)
def remover_source(source_id: int, session: Session = Depends(get_session)):
    s = session.get(SourceConfig, source_id)
    if s is None:
        raise HTTPException(status_code=404, detail="fonte não encontrada")
    session.delete(s)
    session.flush()
    return Response(status_code=204)
